import asyncio,json,pathlib,threading,sys
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from deepseek_harness_runtime import bundled_runtime_path
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[2]))
from app.harness_profile import profile_patch
p=pathlib.Path(__file__).resolve().parent
requests=[]
class FakeProvider(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_POST(self):
  body=json.loads(self.rfile.read(int(self.headers['Content-Length'])));requests.append({'path':self.path,'body':body})
  delta={'role':'assistant','content':'offline probe complete'};finish='stop'
  if len(requests)==1:
   delta={'role':'assistant','content':None,'tool_calls':[{'index':0,'id':'probe-call-1','type':'function','function':{'name':'mcp__probe__echo_probe','arguments':'{"value":"local-only"}'}}]};finish='tool_calls'
  chunks=[{'id':'offline-probe','object':'chat.completion.chunk','created':1,'model':'deepseek-flash','choices':[{'index':0,'delta':delta,'finish_reason':None}]},{'id':'offline-probe','object':'chat.completion.chunk','created':1,'model':'deepseek-flash','choices':[{'index':0,'delta':{},'finish_reason':finish}],'usage':{'prompt_tokens':1,'completion_tokens':1,'total_tokens':2}}]
  content=''.join('data: '+json.dumps(x)+'\n\n' for x in chunks)+'data: [DONE]\n\n'
  self.send_response(200);self.send_header('Content-Type','text/event-stream');self.send_header('Content-Length',str(len(content.encode())));self.end_headers();self.wfile.write(content.encode())
async def main():
 http=ThreadingHTTPServer(('127.0.0.1',0),FakeProvider);thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
 patch=p/'mcp-profile.patch.yml';patch.write_text(json.dumps(profile_patch('deepseek-flash',f'http://127.0.0.1:{http.server_port}/v1',4096,p/'mcp-sessions'),indent=2)+'\n')
 env={'PATH':'/usr/bin:/bin','PKG_NATIVE_CACHE_PATH':str(p/'native-cache'),'DSH_HOME':str(p/'dsh-home'),'FYP_HARNESS_PROXY_TOKEN':'no-real-key-probe'}
 proc=await asyncio.create_subprocess_exec(str(bundled_runtime_path()),'--profile','education','--patch',str(patch),cwd=p,env=env,stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
 stderr=asyncio.create_task(proc.stderr.read());frames=[]
 async def request(i,method,params):
  req={'jsonrpc':'2.0','id':i,'method':method,'params':params};frames.append({'direction':'sent','frame':req});proc.stdin.write((json.dumps(req)+'\n').encode());await proc.stdin.drain()
  while True:
   line=await asyncio.wait_for(proc.stdout.readline(),20)
   if not line:raise RuntimeError('EOF')
   data=json.loads(line);frames.append({'direction':'received','frame':data})
   if data.get('id')==i:return data
 result={}
 try:
  result['initialize']=await request(1,'initialize',{'protocolVersion':1,'clientInfo':{'name':'fyp-offline-probe','version':'1'},'clientCapabilities':{}})
  mcp={'name':'probe','command':sys.executable,'args':[str(p/'mcp_probe_server.py')],'env':[]}
  result['new']=await request(2,'session/new',{'cwd':str(p),'mcpServers':[mcp]})
  print('new',result['new'])
  sid=result['new']['result']['sessionId']
  result['prompt']=await request(3,'session/prompt',{'sessionId':sid,'prompt':[{'type':'text','text':'Run the local echo probe.'}]})
  print('prompt',result['prompt'])
  result['close']=await request(4,'session/close',{'sessionId':sid})
  result['resume']=await request(5,'session/resume',{'sessionId':sid,'cwd':str(p),'mcpServers':[mcp]})
  result['close2']=await request(6,'session/close',{'sessionId':sid})
 except Exception as e:result['error']=repr(e);print('error',repr(e))
 finally:
  proc.stdin.close()
  try:await asyncio.wait_for(proc.wait(),5)
  except TimeoutError:proc.kill();await proc.wait()
  err=(await stderr).decode();http.shutdown();http.server_close();print('exit',proc.returncode,'stderr',err[:3000]);result['exit_code']=proc.returncode
  (p/'mcp-probe.json').write_text(json.dumps({'results':result,'frames':frames,'fake_provider_requests':requests},indent=2)+'\n');(p/'mcp-probe.stderr').write_text(err)
  print('fake provider calls',len(requests),'tool catalog',[[t.get('function',{}).get('name') for t in r['body'].get('tools',[])] for r in requests])
asyncio.run(main())
