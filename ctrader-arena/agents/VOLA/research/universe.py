import json,re
d=json.load(open('/root/.claude/projects/-home-user-treasure/10071b74-ac42-5246-8cff-7de15edfbf7b/tool-results/mcp-ctrader_Demo-get_symbols-1794925758837-3e8p53.txt'))['symbols']
pat=re.compile(r'(crash|boom|jump|dex|range break|snap|flip|skew|trek|exponential|ladder)',re.I)
hold=set(l.split()[0] for l in open('data/.holdout') if l.strip() and not l.startswith('#'))
out=[]
for s in d:
    if pat.search(s['symbolName']):
        out.append((s['symbolId'],s['symbolName'],s.get('description',''),str(s['symbolId']) in hold))
out.sort()
json.dump(out,open('agents/VOLA/research/universe.json','w'),indent=0)
for o in out: print(o[0],o[1],'|',o[2][:70],'' if o[3] else 'NOT_SEALED')
print(len(out))
