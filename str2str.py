#!/usr/bin/python
# from __future__ import print_function

import sys
import argparse
import json
import re
import os
import evalidate
import time
import logging
import logging.handlers
import cPickle as pickle

import time
import datetime
import dateutil.parser 

default_redir = '~/.str2str'


def importredir(path,silent=False):
    ire=[]
    fullpath = os.path.expanduser(path)
    #print "importredir from",path
    try:
        for file in os.listdir(fullpath):
            if file.endswith(".json"):
                #print ".. import file",file
                ire += importre(os.path.join(fullpath, file))
        
        return ire
    except OSError as e:
        if not silent:
            log.warn('not found '+fullpath)
        return []

def importre(filename):
    with open(filename) as json_file:
        try:
            json_data = json.load(json_file)
        except ValueError as e:
            print("Cannot import regexes from JSON file '{}': {}".format(filename,e))
            sys.exit()            
        # compile all regexp structures here
        for rs in json_data:
            rs['filename']=filename
            rs['compiled']=re.compile(rs['re'])
            
            if 'prefilter' in rs:
                try:
                    node = evalidate.evalidate(rs['prefilter'])
                    rs['prefilter_code']=compile(node,'<prefilter>','eval')
                except ValueError as e:
                    log.error('bad prefilter code \'{}\' in {}: {}'.format(rs['prefilter'],filename,str(e)))
                    os.exit(1)
             
    return json_data


def mergedict(x,y):
    z = x.copy()
    z.update(y)
    return z


def datetimeparse(d,name,spec):
    (cmd,utfield, agefield) = spec.split('|')
    dt = dateutil.parser.parse(d[name])
    utime = int(time.mktime(dt.timetuple()))
    
    now = datetime.datetime.now()
    utimenow = int(time.mktime(now.timetuple())) 
    
    age = utimenow - utime
        
    d[utfield]=utime
    d[agefield]=age
    

def process(ire,args,f,filename=None):
    dd=[]
    
    nlines=0
    nrs=len(ire)
    nparse=0
   
    for line in f:
    
        # maybe just skip this line?
        if args.grep and not args.grep in line:
            continue
        
    
        nlines+=1        
        #print "LINE:",line
        d={}
        d['_codename']=[]
        
        lastnewkeys=[]                
        npass=0
        
        while npass==0 or lastnewkeys:
            # print "pass: {} lastnewkeys: {}".format(npass,lastnewkeys)
            newkeys=[]

            for rs in ire:
                # should we try this rs or not?
                # try if it doesn't require keys (and we have first pass)
                # try if it req keys and we added keys on last pass
                                                
                if (rs['input'] is None and not lastnewkeys) or \
                    (rs['input'] is not None and rs['input'] in lastnewkeys):
                      #print "will try rs",rs['name']
            
                    if 'prefilter_code' in rs:
                        if not eval(rs['prefilter_code'],{},d):
                            # prefilter not match, do not use this rs at this pass on this structure
                            continue
                      
                    nparse+=1                       
                    
                    if 'reqs' in rs:
                        for reqname in rs['reqs']:
                            if not reqname in d:
                                # no required field
                                continue
                            if not d[reqname]:
                                # requirement is not true
                                continue
                    
                    if rs['input']:
                        data = d[rs['input']]
                    else:
                        data = line
                    m = rs['compiled'].match(data)
                    if m:
                        #print "match!"
                        gd = m.groupdict()
                        # import keys from this line
                        for k in gd.keys():
                            if not k in d:
                                d[k]=gd[k]
                                newkeys.append(k)
                                # print "append newkey '{}'".format(k)
                        
                        # process specials from this re
                        if 'spec' in rs:
                            for name, spec in rs['spec'].iteritems():
                                if name in d:
                                    if spec=='int':
                                        d[name]=int(float((d[name])))
                                    elif spec=='float':
                                        d[name]=float(d[name])
                                    elif spec.startswith("datetimeparse"):
                                        datetimeparse(d,name,spec)
                        
                        # process settrue from this re
                        if 'settrue' in rs:
                            if isinstance(rs['settrue'],basestring):
                                d[rs['settrue']]=True
                                newkeys.append(rs['settrue'])
                            if isinstance(rs['settrue'],list):
                                for k in rs['settrue']:
                                    d[k]=True
                                    newkeys.append(k)
                        # process codename
                        if 'codename' in rs:
                            d['_codename'].append(rs['codename'])
                            
                    else:
                        # no match
                        pass
                else:
                    pass
                    # print "will skip rs",rs['name']
                 
            # pass is done
            lastnewkeys=newkeys
            npass=npass+1
        dd.append(d)
        
    #print "import statistics:"
    #print "nlines: {}, nrs: {}, nparse: {}".format(nlines,nrs,nparse)
        
    return dd




def group1(d, new, gop):
    if d is None:
        newd = dict()
        newd['_group_gc'] = 0
    else:
        newd = dict(d)
    
    newd['_group_gc'] += 1
        
    for fname in new.keys():
        fvalue = new[fname]
        
        # log.info("join fname {}".format(fname))
        if fname in newd:
            if fname == gop['group']:
                # no need to join key field, it's same
                continue                
            if fname in gop['list']:
                newd[fname].append(fvalue)
            if fname in gop['min']:
                newd['_group_min_'+fname] = min(newd[fname], fvalue)
            if fname in gop['max']:
                newd['_group_max_'+fname] = max(newd[fname], fvalue)
            if fname in gop['last']:
                newd[fname] = fvalue                                   
            
            if fname in gop['name']:
                newfname = '_group_' + str(gc) + '_' + fname
                newd[newfname] = fvalue
                
            if fname in gop['min'] and fname in gop['max']:
                # make delta
                newd['_group_delta_'+fname] = newd['_group_max_'+fname] - newd['_group_min_'+fname]
                            
            # and no handling for 'first'.
                
        else:
            # create field
            if fname in gop['list']:
                newd[fname] = list()
                newd[fname].append(fvalue)
            elif fname in gop['min']:
                newd['_group_min_'+fname] = fvalue
                newd[fname] = fvalue  
            elif fname in gop['max']:
                newd['_group_max_'+fname] = fvalue
                newd[fname] = fvalue                  
            # no special handling for 'first' or 'last' or 'jname':
            else:
                newd[fname] = fvalue

            # special case if both min and max              
            if fname in gop['min'] and fname in gop['max']:
                newd['_group_delta_'+fname] = 0
            
    
    return newd
      


def group(data, gop):
    out = list()
    keyindex = dict()
    
    keyfield = gop['group']
    
    for d in data:
        if not keyfield in d:
            # discard it, cannot group
            continue
        key = d[keyfield]
        if key in keyindex:
            pos = keyindex[key]
            nd = group1(out[pos],d,gop)
            out[pos] = nd
        else:
            nd = group1(None,d,gop)
            out.append(nd)
            pos = len(out)-1
            keyindex[key] = pos
    
    
    return out

def mkargparse():
    parser = argparse.ArgumentParser(description='str2str: string to struct converter')
    
    gconf = parser.add_argument_group('Loading configuration', description='# if nothing specified, config files (*.json) loaded from default --redir')
    ginput = parser.add_argument_group('Input data')
    gfilter = parser.add_argument_group('Filtering')
    gpost = parser.add_argument_group('Post-processing')
    goutput = parser.add_argument_group('Output data')

    # general options
    parser.add_argument('-v',dest='v',default=0, help='verbose', action='count')
    
    # group conf
    gconf.add_argument('--re', metavar='filename.json', dest='re', help='import regexes from filename ', default=None, action='append')
    gconf.add_argument('--redir', metavar='DIR', dest='redir', help='import all json regex files from this dir (default: {})'.format(default_redir), default=default_redir)
    gconf.add_argument('--codename', metavar='CODENAME', dest='codename', help='process only this codename(s). For debug or speed-up.', default=None, action='append')
    
    
    # group input
    ginput.add_argument('-f', dest='filename', default=None, help='text file name (default: stdin)', action='append')
    ginput.add_argument('--grep', dest='grep', default=None, help='load only strings which has this text')
    ginput.add_argument('--pload',dest='pload', metavar="FILENAME.p", default=False, help='load pre-parsed data as pickle serialized object')    
    ginput.add_argument('--jload',dest='jload', default=False, action='store_true', help='Do not parse by regexes, load data from pre-parsed json (saved with --jdump before)')    

    # group filter
    gfilter.add_argument('--filter',dest='filter',default=None, help='evalidate filtering expression')

    # group postprocessing
    gpost.add_argument('--sort',dest='sort',metavar="FIELD", default=None, help='sort by value of field')
    gpost.add_argument('--head',dest='head',metavar="NUM", default=None, help='leave only first NUM records', type=int)
    gpost.add_argument('--tail',dest='tail',metavar="NUM", default=None, help='leave only last NUM records',type=int)
    gpost.add_argument('--reverse',dest='reverse', default=False, action='store_true', help='Reverse resulting list')
    gpost.add_argument('--rmkey', dest='rmkey', metavar="KEY", default=[], help='delete key (if exists)', action='append')
    gpost.add_argument('--onlykey', dest='onlykey', metavar="KEY", default=[], help='delete all keys except these (multiple)', action='append')
    gpost.add_argument('--group', dest='group', metavar="FIELD", default=None, help='group by same key-field')
    gpost.add_argument('--gname', dest='gname', metavar="FIELD", default=[], action='append', help='overlap: name')
    gpost.add_argument('--glist', dest='glist', metavar="FIELD", default=[], action='append', help='overlap: list')
    gpost.add_argument('--gmin', dest='gmin', metavar="FIELD", default=[], action='append', help='overlap: min')
    gpost.add_argument('--gmax', dest='gmax', metavar="FIELD", default=[], action='append', help='overlap: max')
    gpost.add_argument('--gfirst', dest='gfirst', metavar="FIELD", default=[], action='append', help='overlap: first')
    gpost.add_argument('--glast', dest='glast', metavar="FIELD", default=[], action='append', help='overlap: last')

    
    # group output
    goutput.add_argument('--dump',dest='dump', default=False, action='store_true', help='out data with python pring (not really useful)')    
    goutput.add_argument('--jdump',dest='jdump', default=False, action='store_true', help='out data in json format (list of dicts)')    
    goutput.add_argument('--pdump',dest='pdump', metavar="FILENAME.p", default=False, help='save parsed data as pickle serialized object')    
    goutput.add_argument('--fmt',dest='fmt', default=None, help='print in format') 
    goutput.add_argument('--key',dest='key', default=None, action='append', help='print keys (multiple)') 
    goutput.add_argument('--keysep',dest='keysep', default=' ', help='separator for keys') 
    goutput.add_argument('--keynames',dest='keynames', default=False, action='store_true', help='print also keynames (for --key)') 
    goutput.add_argument('--count',dest='count', default=False, action='store_true', help='print count of records') 
    goutput.add_argument('--sum',dest='sum', metavar='FIELD', default=False,    help='calculate and print sum of field') 
    goutput.add_argument('--avg',dest='avg', metavar='FIELD', default=False, help='calculate and print average of field') 


    return parser

#### main ####
ap = mkargparse()
args = ap.parse_args()


log = logging.getLogger('MyLogger')
log.setLevel(logging.DEBUG)
ch = logging.StreamHandler( sys.__stderr__ )
if args.v==0:
    ch.setLevel(logging.WARNING)
if args.v==1:
    ch.setLevel(logging.INFO)
if args.v>=2:
    ch.setLevel(logging.DEBUG)


formatter = logging.Formatter('%(asctime)s %(message)s')
ch.setFormatter(formatter)
log.addHandler(ch)

log.info("str2str started, verbosity: {}".format(args.v))
    
# pre-STAGE: import regex
log.info("pre-stage: load filters")


if args.redir == default_redir and not args.v:
    silent=True
else:
    silent=False
    
ire=importredir(args.redir,silent)



if args.re is not None:
    for refile in args.re:
        ire += importre(refile)

re_imported=0
re_ignored=0

if args.codename:
    new_ire = []
    for ir in ire:
        if 'codename' in ir:
            if ir['codename'] in args.codename:
                # leave this
                log.info('load rule with codename {}'.format(ir['codename']))                
                new_ire.append(ir)
                re_imported += 1
            else:
                log.info('skip rule with codename {}'.format(ir['codename']))                
                re_ignored += 1
        else:
            log.info('skip noname rule')                
            re_ignored += 1
                
    ire = new_ire

else:
    re_imported = len(ire)

log.info("Imported {} rules, ignored {} rules.".format(re_imported, re_ignored))


# STAGE 1: import data
log.info("stage 1: load data")
    
if args.filename is not None:
    for filename in args.filename:
        with open(filename) as logfile:
            if args.jload:
                # load from pre-parsed json file
                try:
                    dd = json.load(logfile)
                except ValueError as e:
                    print("Cannot import regexes from JSON file '{}': {}".format(filename,e))
                    sys.exit()
            else:
                # load from strings file
                dd = process(ire,args,logfile,filename=filename)
                

else:
    # no filename specified
    if args.pload:
        # import from pickle
        dd = pickle.load(open(args.pload,"rb"))
    elif args.jload:
        # load from stdin JSON
        try:
            dd = json.load(sys.stdin)
        except ValueError as e:
            print("Cannot import regexes from stdin file: {}".format(filename,e))
            sys.exit()
    else:
        # load from STDIN strings
        dd = process(ire,args,sys.stdin,filename="<STDIN>")



# STAGE 2: filter data
log.info("stage 2: filter")

if args.filter:
    log.info("filter by expression: "+args.filter)
    newdd=[]
    try:
        node = evalidate.evalidate(args.filter)
        code = compile(node,'<userfilter>','eval')
        for d in dd:                
            log.debug("filter structure:"+str(d))       
            try:
                if eval(code,{},d):
                    log.debug("filter OK")
                    newdd.append(d)
                else:                
                    log.debug("filter FAIL")
                    pass
            except NameError as e:
                log.debug("filter FAIL {}".format(e))
                
        dd = newdd
            
    except ValueError as e:
        log.error("Bad filter code: {} exception: {}".format(args.filter, e))
        sys.exit(1)
        

# STAGE 3: postprocessing (sorting)
log.info("stage 3: postprocessing")

if args.group:
    gop = dict()
    gop['group'] = args.group
    gop['list'] = args.glist
    gop['name'] = args.gname
    gop['min'] = args.gmin
    gop['max'] = args.gmax
    gop['first'] = args.gfirst
    gop['last'] = args.glast

    dd = group(dd, gop)

if args.sort:
    dd = sorted(dd, key = lambda i: i[args.sort], reverse=args.reverse)

if args.reverse:
    dd = list(reversed(dd))

if args.rmkey:
    for d in dd:
        for nk in args.rmkey:
            if nk in d:
                del d[nk]


if args.onlykey:
    for d in dd:
        for k in d.keys():
            if not k in args.onlykey:
                del d[k]

if args.head:
    dd = dd[:args.head]    

if args.tail:
    startpos=len(dd)-args.tail
    if startpos<0:
        startpos=0
    dd = dd[startpos:]

# STAGE 4: output
log.info("stage 4: output results")


if args.dump:
    for d in dd:
        print(d)

if args.jdump:
    print(json.dumps(dd, sort_keys=True, indent=4, separators=[',', ': ']))

if args.fmt:
    for d in dd:
        print(args.fmt.format(**d))
        
if args.key:        
    for d in dd:
        outstr=""
        
        for k in args.key:        
            if k in d:
                if outstr:
                    outstr+=args.keysep
                if args.keynames:
                    outstr+=k+": "
                outstr+=str(d[k])        
        if outstr:
            print(outstr)

if args.count:
    print len(dd)

if args.sum:
    s=0
    for d in dd:
        s+=d[args.sum]
    print s

if args.avg:
    s=0
    n=0
    for d in dd:
        n+=1
        s+=d[args.avg]
    avg=s/n
    print avg


if args.pdump:
    pickle.dump(dd,open(args.pdump,"wb",-1))
    
log.info("str2str done")
    
