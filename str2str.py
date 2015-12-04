#!/usr/bin/python
from __future__ import print_function

import sys
import argparse
import json
import re
import os
import evalidate
import time
import logging
import logging.handlers


def importredir(path):
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
    return json_data


def mergedict(x,y):
    z = x.copy()
    z.update(y)
    return z

def process(ire,args,f,filename=None):
    dd=[]
    
    nlines=0
    nrs=len(ire)
    nparse=0
   
    for line in f:
        nlines+=1        
        #print "LINE:",line
        d={}
        
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
                    
                    nparse+=1   
                    
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
                        # process settrue from this re
                        if 'settrue' in rs:
                            if isinstance(rs['settrue'],basestring):
                                d[rs['settrue']]=True
                                newkeys.append(rs['settrue'])
                            if isinstance(rs['settrue'],list):
                                for k in rs['settrue']:
                                    d[k]=True
                                    newkeys.append(k)
                            
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


def mkargparse():
    parser = argparse.ArgumentParser(description='str2str: string to struct converter')
    parser.add_argument('--re', metavar='filename.json', dest='re', help='import regexes from filename ', default=None, action='append')
    parser.add_argument('--redir', metavar='DIR', dest='redir', help='import all json regex files from this dir', default="~/.str2str", action='append')
    parser.add_argument('-f', dest='filename', default=None, help='text file name (default: stdin)', action='append')
    parser.add_argument('--dump',dest='dump', default=False, action='store_true', help='out data with python pring (not really useful)')    
    parser.add_argument('--jdump',dest='jdump', default=False, action='store_true', help='out data in json format (list of dicts)')    
    parser.add_argument('--jload',dest='jload', default=False, action='store_true', help='Do not parse, load pre-parsed json (saved with --jdump before)')    
    parser.add_argument('--fmt',dest='fmt', default=None, help='print in format') 
    parser.add_argument('--key',dest='key', default=None, action='append', help='print keys (multiple)') 
    parser.add_argument('--keynames',dest='keynames', default=False, action='store_true', help='print also keynames (for --key)') 
    parser.add_argument('--filter',dest='filter',default=None, help='evalidate filtering expression')
    parser.add_argument('-v',dest='v',default=0, help='verbose', action='count')

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
    
# STAGE 1: import regex
log.info("load filters")

ire=importredir(args.redir)

if args.re is not None:
    for re in args.re:
        ire += importre(i)


# STAGE 2: import data
log.info("load data")
    
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
    if args.jload:
        # load from pre-parsed json file
        try:
            dd = json.load(sys.stdin)
        except ValueError as e:
            print("Cannot import regexes from stdin file: {}".format(filename,e))
            sys.exit()
    else:
        # load from strings file
        dd = process(ire,args,sys.stdin,filename="<STDIN>")



# STAGE 3: filter data
log.info("filter")

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
        timestderr("Bad filter code:", args.filter, e)
        sys.exit(1)
        


# STAGE 4: output
log.info("output results")


if args.dump:
    for d in dd:
        print(d)

if args.jdump:
    print(json.dumps(dd, sort_keys=True, indent=4, separators=[',', ': ']))

if args.fmt:
    print("format:",args.fmt)
    for d in dd:
        print(args.fmt.format(**d))
        
if args.key:        
    for d in dd:
        outstr=""
        
        for k in args.key:        
            if k in d:
                if outstr:
                    outstr+=" "
                if args.keynames:
                    outstr+=k+": "
                outstr+=d[k]        
        if outstr:
            print(outstr)
    
log.info("str2str done")
    
