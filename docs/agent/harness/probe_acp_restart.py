import asyncio,json,pathlib,sys
from deepseek_harness_runtime import bundled_runtime_path
p=pathlib.Path(__file__).resolve().parent
async def main():
 env={'PATH':'/usr/bin:/bin','PKG_NATIVE_CACHE_PATH':str(p/'native-cache'),'DSH_HOME':str(p/'dsh-home'),'FYP_HARNESS_PROXY_TOKEN':'no-real-key-probe'}
 proc=await asyncio.create_subprocess_exec(str(bundled_runtime_path()),'--profile','education','--patch',str(p/(sys.argv[1] if len(sys.argv)>1 else 'education.patch.yml')),cwd=p,env=env,stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
 stderr=asyncio.create_task(proc.stderr.read()); frames=[]
 async def request(i,method,params):
  req={'jsonrpc':'2.0','id':i,'method':method,'params':params};frames.append({'direction':'sent','frame':req});proc.stdin.write((json.dumps(req)+'\n').encode());await proc.stdin.drain()
  while True:
   line=await asyncio.wait_for(proc.stdout.readline(),20)
   if not line: raise RuntimeError('runtime EOF')
   d=json.loads(line);frames.append({'direction':'received','frame':d})
   if d.get('id')==i:return d
 try:
  print('initialize',await request(1,'initialize',{'protocolVersion':1,'clientInfo':{'name':'fyp-install-probe','version':'1'},'clientCapabilities':{}}))
  old=json.loads((p/'acp-handshake.json').read_text())
  sid=next(x['frame']['result']['sessionId'] for x in old if x['direction']=='received' and x['frame'].get('id')==2)
  print('resume_previous_process',await request(2,'session/resume',{'sessionId':sid,'cwd':str(p),'mcpServers':[]}))
  print('close',await request(3,'session/close',{'sessionId':sid}))

 except Exception as e: print(type(e).__name__,str(e))
 finally:
  proc.stdin.close()
  try: await asyncio.wait_for(proc.wait(),5)
  except TimeoutError: proc.kill();await proc.wait()
  err=(await stderr).decode();print('exit',proc.returncode,'stderr',err[:15000]);(p/'acp-restart-handshake.json').write_text(json.dumps(frames,indent=2)+'\n');(p/'acp-restart-handshake.stderr').write_text(err)
asyncio.run(main())
