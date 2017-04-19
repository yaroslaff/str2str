# str2str: String to Structure


## Purpose
str2str is smart `grep` or `awk` alternative. Mainly for loading usual plaintext file (most often: log file), converting to to data structures (using library of regexes), optional filtering by logical expression and then output filtered data in plain or JSON format.

## str2str vs grep

Most of things str2str can do, you can do with grep, sort and other utilities. But str2str makes it easier.

**Undestanding** Str2str can understand value of each field in log record and perform logical expressions, like "if email message size is large then X" or "count summary size for 5 largest .ISO downloads in apache access.log". 

It's possible to compare many values in same record. E.g. if you have online shop and log of all purchases, like:
`DATE TIME user #123 purchase #1234567 total sum: $1020 max price: $800` you can distinguish:

- single purchase (total sum is same as price of most expensive item)
- purchase of big item and accessories (TV for $1000 and cables for $50)
- many purchases (total sum is over $2200, max price less or equal then 50% or total sum. Like if person bought two TV)

**Write regex once**. Rules with regexes for str2str are stored in configuration files. If you write complex regex today and save it in str2str config, then after few month you can re-use it simple, no need to rewrite complex regex again. 

**Aggregation**. Not all data available as substring in log line. Some data is 'between the lines'. Simple example:
~~~
01-01-1991 01:02 Message ID ABC123DEF456 accepted
~~~
and 
~~~
01-01-2017 01:03 Message ID ABC123DEF456 delivered
~~~
Each line alone looking very boring and ordinary. But...
~~~
01-01-1991 01:02 Message ID ABC123DEF456 accepted
01-01-2017 01:03 Message ID ABC123DEF456 delivered
~~~
Now this is very interesting! More then 26 years in queue! We defenitely need to debug our mailserver (and probably upgrade it, Intel 486DX from 1991 is little too slow. As we see.)

Minimal, maximal, average, delta, count and sum - always between the lines and cannot be analyzed by simple line-by-line grepping. 

With simple grep it's not possible at all to work with such data, because each log record alone looks ordinary.

**Formats**. str2str can take and return data in any text format (as it was in log, in JSON or in formatted string). So, it's good as an glue in unix pipe between commands. (e.g. take JSON data of Amazon Glacier backups and print only file names)



## Examples

Please note, str2str is an 'engine' and may require manual tuning for your format of log files if it's little different from our format.

### Display large emails

    ./str2str.py -f /var/log/mail.log --filter 'qmgr and size>1000000' --fmt "{from} {size}" 

This is assuming str2str was properly installed and regex filters are in ~/.str2str. If not, full command should manually import regex files like this:

    ./str2str.py --re importre.json --re postfix.json -f /var/log/mail.log --filter 'qmgr and size>1000000' --fmt "{from} {size}" 

Calculate summary:

    $ ./str2str.py -f /var/log/mail.log --filter 'qmgr and size>1000000' --sum size
    43985776

Display only 5 biggest emails in log file:
~~~
./str2str.py -f /var/log/mail.log --filter 'qmgr' --sort size --tail 5 --fmt "{size}: {from}"
450022: info@example.com
755675: i.petrov@example.com
3653972: j.doe@example.com
4529035: b.gates@example.com
10908592: batman@example.com
~~~

### Time to deliver
~~~
$ ./str2str.py -f /var/log/mail.log --group msgid --count
532
~~~
Each message may have many lines in mail.log, and also other mailing software (postgrey, amavis, dovecot) writes there, so wc -l /var/log/mail.log is useless. With str2str we know we have 532 messages logged.

~~~
$ ./str2str.py -f /var/log/mail.log --group msgid --gmax log_unixtime --gmin log_unixtime --avg _group_delta_log_unixtime 
2
~~~
In average, message stays in queue for 2 seconds. (time between minimal asnd maximal log_unixtime records for same message id)

Now lets see unusual messages:

~~~
$ ./str2str.py -f /var/log/mail.log --group msgid --gmax log_unixtime --gmin log_unixtime --sort _group_delta_log_unixtime  --tail 5 --fmt '{msgid} {_group_delta_log_unixtime}'
5CE4462513 31
8B8356169C 42
1E2AB61666 60
A4728624DD 63
3819A62551 308
~~~

Totally we had 10'000 records in log file. After --group there were 532 messages. Usually message is processed in 2s, sometimes, as we see, it takes 30-60 seconds, but 3819A62551 took 300 seconds! Maybe something is wrong? We should investigate logs for misterious message id 3819A62551. 


### Display archive name and size from Amazon Glacier in nice format

    glacier-cmd --output json inventory MyInventoryName | /usr/local/bin/str2str.py  --jload --fmt "{ArchiveDescription} {Size}"
    opt-vzdump-openvz-105-2017_03_22-05_05_16.tgz 3911368733
    mail-vzdump-openvz-101-2017_03_22-07_35_01.tgz 14201001975
    nl2-vzdump-openvz-102-2017_03_22-09_08_46.tgz 15222806360
    ...


## Installation and preprequisites 

### Preprequisites
    pip install python-dateutil
    pip install evalidate

### Install
    git clone https://github.com/yaroslaff/str2str    
    mkdir ~/.str2str
    cp str2str/*.json ~/.str2str

## Four stages of processing

Each run of str2str passes 4 optional stages. Functions in same stage are runs in order which is most often used, e.g. sorting runs after grouping (both on postprocessing stage #3), and filtering runs on stage #2. 

If you need some function to run AFTER other function, which runs usually BEFORE it, or if you need to run it twice (e.g. filter records before grouping, and then filter grouped records again) you can run str2str in unix pipe, something like this:
~~~
$ ./str2str --filter ... --group ... --jdump | ./str2str --jload --filter ...
~~~

first str2str process will run filter and then group, output data in JSON format. Second str2str process will take this data and filter it again.

### Stage 1: Input
Loading data from file (`-f`) or from stdin. Data can be just strings (like log file), or list of objects in JSON format, or pickle serialized object.

- `-f <FILENAME>` - load from this file, not from stdin
- `--json` - load data as JSON
- `--pload <FILENAME>` - load data as pickle object
- `--grep <SUBSTRING>` - load only strings with this substring (to speed-up process).

When data is read, it's parsed (according to loaded regexes). For each imported line, str2str creates object with fields extracted from log line.

pload used as an pair with pdump. For many runs (e.g in testing), it could be better to parse log file once and `--pdump` it. `--pload` it much faster then usual loading.

### Stage 2: Filtering
Filtering is optional step, there is only one option for it:

- - `--filter 'EXPRESSION'` - filter list of objects (e.g. log lines) by python-style expression.

For example:
- For postfix mail.log, after filtering we may want to have only lines about sent messages, or only about large sent messages.
- For apache access.log, wa may want to have data only about POST requests.

str2str uses `evalidate` python module for this filtering.

### Stage 3: Post-processing

- `--sort FIELD` - sort log records (objects in list) by this field
- `--reverse` - if `sort` used, reverses list.
- `--head NUM`, `--tail NUM` - leave only NUM records at head or tail of list
- `--rmkey KEY` - delete keys from records (can be used multiple times)
- `--onlykey KEY` - delete all keys from record except keys in this options.

rmkey and onlykey are useful only to make data shorter and easier to read.

Example:
~~~
./str2str.py -f /var/log/mail.log --filter 'qmgr' --sort size --tail 15 --jdump --onlykey log_msg --onlykey size
[    
    {
        "log_msg": "BAF7062513: from=<laura.hidden@example.com>, size=4529824, nrcpt=1 (queue active)",
        "size": 4529824
    },
    {
        "log_msg": "AA8BF60B5F: from=<big.ben@example.com>, size=10908592, nrcpt=1 (queue active)",
        "size": 10908592
    }
    ...
~~~

#### GROUPS
str2str can group records together. options:

`--group FIELD` if this option is used, all records with same values of FIELD will be grouped together.
If field exist in at least one grouping record, it will be in resulting (grouped) record. So, if record 1 has fields AA and BB, and record 2 has fields AA and CC, final record will have fields AA, BB and CC.

What if fields are overlapping (two or more records has fields of same name)? str2str behavior will depend on options `--gname`,`--glist`, `--gmin`, `--gmax`, `--gfirst` and `--glast`. Each of this option accepts one field name as argument, and this field will be processed by specific method. Options could be specified multiple time.

if `--gname FIELD` was used, then new field is created for each new value. field name will be `_group_GC_FIELD` where GC is number of this group operation and FIELD is field name.

if `--glist FIELD` was used, FIELD will be list, and each new value is append to this list.

if `--gmin FIELD` was used, FIELD will have first value (unless it's also given in --glast FIELD), but special field `_group_min_FIELD` will be created and it will have minimal value of this field among all grouped fields.

if `--gmax FIELD` was used, FIELD will have first value (unless it's also given in --glast FIELD), but special field `_group_max_FIELD` will be created and it will have maximal value of this field among all grouped fields.

**Note:** if both `--gmin FIELD` and `--gmax FIELD` was used, there will be also `_group_delta_FIELD` field with difference between max and min value.

if `--glast FIELD` was used, FIELD will have value of last field.

if `--gfirst FIELD` was used, FIELD will have value of first field (never will be overwritten by new values).

On each grouping operation, `_group_gc` field is incremented, so you can see how many records are grouped in record.

Grouping performed before sorting, so you can sort data based on fields which will be generated during grouping.

f
### Stage 4: Output

- `--dump` - output data as simple python print does. (not very useful. --jdump is better.
- `--jdump` - output data as pretty formatted JSON
- `--pdump FILENAME.p` - write serialized object to file to use later with --pload. 
- `--fmt FORMAT` - write each record as formatted line. {fieldname} replaced by value of field.
- `--key KEY` - (multiple). Print values of this keys separated by separator (default - space).
- `--keysep SEP` - separator (string), used by --key
- `--keyname` - user by --key. if given, each key is printed as KEY: VALUE instead of just VALUE.
- `--count` - print count of records. something like wc -l would do for output.
- `--sum FIELD` - print sum of all values of this field in all record
- `--avg FIELD` - print average for this field 

Note: --sum and --avg requires all records to have this field. If some records miss this field - sum and avg will not work. use `--filter FIELD` to pre-filter data and leave only records which has this field.

MSGID for largest messages:
~~~
$ ./str2str.py -f /var/log/mail.log --filter 'qmgr' --sort size --tail 5 --key size --key msgid --keysep ' :: ' --keynames
size: 1236381 :: msgid: 5C61360AE8
size: 1663464 :: msgid: 0FF67622DC
size: 3653166 :: msgid: 8B30961718
size: 4529035 :: msgid: 67CE960B5F
size: 10908592 :: msgid: AA8BF60B5F
~~~

Sum size of all messages in log:
~~~
./str2str.py -f /var/log/mail.log --filter 'qmgr' --sum size
65313543
~~~

Average size of message:
~~~
$ ./str2str.py -f /var/log/mail.log --filter 'qmgr' --avg size
129078
~~~

## Other command line arguments

- `-v` - verbose mode.
- `--codename` (multiple). load only rules with this codename. (to speed-up processing). 
- `--re FILENAME` - load custom regex file

Example:
~~~
$ ./str2str.py -f /var/log/mail.log --codename anyline --head 1 --jdump
[
    {
        "_codename": [
            "anyline"
        ],
        "log_line": "Apr 18 10:23:11 mx postfix/smtpd[22246]: 58197624B0: client=mx[127.0.0.1]"
    }
]
~~~

## Parsing and regex files 

Now, lets go deeper. Each regext file is 'list of objects' (in JSON therminology), each object represent *rule* for processing. 

After rules are loaded, and str2str loads data, it apples all rules to each record. Each *rule* can add more fields to log record object.

Please note: While regex files are 'list of objects' and data files (log files) are processed into list of objects too, they are very different. When we talk about 'record' or 'log record' or 'log line', we are talking about object of data file (log), not about objects in regex file. Regex file objects are called *rules*.

### Basic fields

Basic fields are: `input`, `desc`, `name`, `re`, `codename`.

Lets see first object (*anyline*) of importre.json:
~~~
    {
        "input": null,
        "desc": "syslog generic line",
        "re": "(?P<log_line>.*)\r?\n?",
        "codename": "anyline"        
    },
~~~
This is root of processing.

`input`: tells what data will be analized. If `null` (like here) - it's applied for raw data (log line). Otherwise, it's applied to field name in object.

str2str is smart enough, and it auto detects in which order rules must be processed.

`desc`: is just an description. Same as `name`. It's not used by str2str. But better to use desc in your custom rules.

`codename`: is important unique identifier of rule. Optional. log object has field _codename: list of all rules (which has codename) which was successfully applied to this log record object. If rule has codename, it's possible to use it separately (by option '--codename') for faster processing.

`re`: regex. Does main work. It tries to apply regex to input data. And if data matches regex, it adds all extracted fields to log record object.  So, this line just makes field 'log_line' without trailing newline.

Example:
~~~
$ ./str2str.py -f /var/log/mail.log --codename anyline --head 1 --jdump
[
    {
        "_codename": [
            "anyline"
        ],
        "log_line": "Apr 18 10:23:11 mx postfix/smtpd[22246]: 58197624B0: client=mx[127.0.0.1]"
    }
]
~~~

This rule generated field log_line (without newline). Also, field _codename is list of all rules (by codename) applied to this log line.

### spec
Now, lets move to next basic rule (*syslog*):
~~~
    {
        "input": "log_line",
        "desc": "extract datetime and loghost",
        "re": "^(?P<log_strtime>[^ ]+ +[^ ]+ +[0-9]+:[0-9]+:[0-9]+) (?P<log_host>[^ ]+) (?P<appstr>[^:]+): (?P<log_msg>.*)",
        "codename": "syslog",
        "spec": {
            "log_strtime": "datetimeparse|log_unixtime|log_age"
        }                
    },
~~~

input here is "log_line", so rule will be applied only to objects with field 'log_line'.

Just lets see it by example:
~~~
$ ./str2str.py --re importre.json --re postfix.json -f /tmp/mail10k.log --codename anyline --codename syslog --head 1 --jdump
[
    {
        "_codename": [
            "anyline",
            "syslog"
        ],
        "appstr": "postfix/smtpd[22246]",
        "log_age": 30455,
        "log_host": "mx",
        "log_line": "Apr 18 10:23:11 mx postfix/smtpd[22246]: 58197624B0: client=mx[127.0.0.1]",
        "log_msg": "58197624B0: client=mx[127.0.0.1]",
        "log_strtime": "Apr 18 10:23:11",
        "log_unixtime": 1492485791
    }
]
~~~

So, this rule created many fields: appstr, log_age, log_host, log_msg, log_strtime and log_unixtime.

For log_strtime, log_host, appstr and log_msg - it was extracted from log_line by regex. Simple. But how log_age, log_unixtime added? It was created by **SPECIAL** procedure **datetimeparse**, built in str2str.

Rule has this part:

        "spec": {
            "log_strtime": "datetimeparse|log_unixtime|log_age"
        }                

`spec` is list of special procedures and their arguments which will be applied to log record object after regex.

`datetimeparse` is special procedure. It takes input (log_strtime), and writes two other fields (here fields are log_unixtime and log_age). First is 'unixtime' of this data, and 2nd is age in second between unixtime and now. 

If we will run this command again, we will see all data is same except 'age'. Age should grow with time.

Other special procedures are `int` and `float` which converts field to this format. (this needed for further processing: filtering and counting sum or average values)

### settrue
`settrue` is very simple. It set field with value 'True'. e.g.:
~~~
    {
        "input": "log_msg",
        "name": "policyd quotas",
        "re": "^module=Quotas, [^,]+, host=(?P<host>[^,]+), [^,]+, from=(?P<from>[^,]+), to=(?P<to>[^,]+), reason=(?P<reason>[^,]+), policy=[0-9]+, quota=[0-9]+, limit=[0-9]+, track=(?P<track>[^,]+), counter=(?P<counter>[^,]+), quota=(?P<quota>[^ ]+) \\((?P<percents>[^%]+)%\\)",
        "settrue": "policyd",
        "spec": {
            "percents": "float"
        }
    },
~~~
This rule processes postfix policyd messages. Each line processed by this rule will have field 'policyd' set to True. This is very useful for filtering, to process only this kind of records with `--filter policyd`.

### reqs
reqs is list of required fields. Rule is applied only when all required fields are present and evaluated as True (non-empty). 

Example:
~~~
    {
        "input": "appname",
        "desc": "set postfix flag for all postfix/*",
        "re": "postfix/.*",
        "settrue": "postfix"
    },
    {
        "input": "log_msg",
		"re": "^(?P<msgid>[0-9A-F]+):.*",
		"reqs": ["postfix"]		
    }
~~~

Postfix log files has many lines of different format but matching template "MSGID: something". MSGID is few hexadecimal digits. We cannot just use 2nd rule, because it would match log line "ABBA: winner of Eurovision 1976". This is strange line to find in mail.log, but it's defenitely not related to postfix. We should process only records from postfix/* app.


## Speed-up advices
str2str can be little slow if log file are large and you have many regex rules. For manual work in shell it's not a big problem, waiting few seconds is okay. But if using in script, which will run many times in a day, better to make it faster.

### grep
Use --grep if you need to analyze only particular lines in log. --grep is very fast. Compare:
~~~
$ time ./str2str.py -f /var/log/mail.log --filter size --sum size
65313543

real	0m4.789s
user	0m4.692s
sys	0m0.096s
$ time ./str2str.py --grep size -f /var/log/mail.log --filter size --sum size
65313543

real	0m0.903s
user	0m0.858s
sys	0m0.044s
~~~
About 5 times faster with just one --grep.

### codename
Instead of trying to apply all known regex (all rules), you can apply only rules which are needed. You can do one run without such optimization, examine _codename in output, and then run it again with --codename options.

~~~
$ time ./str2str.py -f /var/log/mail.log --filter size --sum size --codename anyline --codename syslog --codename qmgr
65313543

real	0m3.901s
user	0m3.755s
sys	0m0.144s
~~~

### pdump/pload
If need to do many operations on same data and with same rules, you can save parsed data (after step 1) and load it later again:
Save:
~~~
$ time ./str2str.py -f /var/log/mail.log --pdump mail.p

real	0m4.527s
user	0m4.358s
sys	0m0.151s
~~~

processing/saving - takes almost same time. Lets see how long processing will take:
~~~
$ time ./str2str.py --pload mail.p --filter size --sum size
65313543

real	0m1.504s
user	0m1.448s
sys	0m0.056s
~~~

1.5 sec vs 4.7 sec.
