"""素材、目录容量及自有服务器协议的独立回归检查。"""
from pathlib import Path
import sys,tempfile,json,threading,time,unittest,hashlib
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));import portable_launcher
from campaign_catalog import Catalog
from community_content import load_manifest
from content_assets import import_png,decode_obm
from online_session import OnlineClient,validate_snapshot,fingerprint
from room_server import RoomServer
from PIL import Image

class ContentTests(unittest.TestCase):
    def test_png_16_bit_rgb_rejected(self):
        import struct,zlib
        def chunk(name,data):return struct.pack('!I',len(data))+name+data+struct.pack('!I',zlib.crc32(name+data))
        raw=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('!IIBBBBB',1,1,16,2,0,0,0))+chunk(b'IDAT',zlib.compress(b'\x00\xff\xff\x80\x00\x00\x00'))+chunk(b'IEND',b'')
        with tempfile.TemporaryDirectory() as temp:
            source=Path(temp)/'rgb16.png';dest=Path(temp)/'asset.obm';source.write_bytes(raw)
            with self.assertRaises(ValueError):import_png(source,dest)
            self.assertFalse(dest.exists())
    def test_png_roundtrip_and_padding(self):
        with tempfile.TemporaryDirectory() as temp:
            source=Path(temp)/'asset.png';dest=Path(temp)/'asset.obm'
            image=Image.new('RGBA',(37,19),(83,110,155,255));image.putpixel((2,3),(255,0,0,120));image.save(source)
            original=source.read_bytes();result=import_png(source,dest)
            self.assertEqual(result['size'],[64,32]);self.assertEqual(source.read_bytes(),original)
            size,raw=decode_obm(dest.read_bytes());out=Image.frombytes('RGBA',size,raw)
            self.assertEqual(out.crop((0,0,37,19)).tobytes(),image.tobytes());self.assertEqual(out.getpixel((40,2)),(0,0,0,0))
    def test_png_color_limit(self):
        with tempfile.TemporaryDirectory() as temp:
            source=Path(temp)/'asset.png';dest=Path(temp)/'asset.obm';image=Image.new('RGBA',(256,1))
            image.putdata([(i,1,3,255) for i in range(256)]);image.save(source)
            with self.assertRaises(ValueError):import_png(source,dest)
            self.assertFalse(dest.exists())
    def test_large_catalog(self):
        units=load_manifest(ROOT/'community_content')[0]['units']
        data={'schema':1,'assets':{},'scenes':[],'music':[],'worlds':[]}
        for w in range(8):
            stages=[{'key':f'test.w{w}.s{i}','title':f'关卡 {i}','scene':0,'enemies':[{'unit':units[i%6]['key']}],
                     'waves':[{'tick':0,'enemy':0}],'requires':[f'test.w{w}.s{i-1}'] if i else []} for i in range(1250)]
            data['worlds'].append({'key':f'test.w{w}','title':f'世界 {w}','areas':[{'key':f'test.w{w}.area','title':'区域','stages':stages}]})
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'catalog.json';path.write_text(json.dumps(data),encoding='utf-8');catalog=Catalog(temp,units)
            self.assertEqual(len(catalog.stages),10000)
            manifest={'schema':2,'units':units,'stages':[]};before=fingerprint(manifest,catalog)
            self.assertEqual(fingerprint(dict(manifest,stages=[]),catalog),before)
            self.assertNotEqual(fingerprint(manifest,catalog,'a'*64),fingerprint(manifest,catalog,'b'*64))
    def test_unlock_cycle(self):
        units=load_manifest(ROOT/'community_content')[0]['units']
        data=json.loads((ROOT/'campaign_content/catalog.example.json').read_text(encoding='utf-8'))
        data['worlds'][0]['requires']=['author.world4.area1.stage1']
        with tempfile.TemporaryDirectory() as temp:
            (Path(temp)/'catalog.json').write_text(json.dumps(data),encoding='utf-8')
            with self.assertRaises(ValueError):Catalog(temp,units)
    def test_mod_campaign_fragment(self):
        # 模组片段（M5）：键前缀、可见范围、与本体目录合并。
        units=load_manifest(ROOT/'community_content')[0]['units']
        body=json.loads((ROOT/'campaign_content/catalog.example.json').read_text(encoding='utf-8'))
        stage={'key':'m.w.a.s','title':'S','scene':0,'enemies':[{'unit':3}],'waves':[{'tick':0,'enemy':0}],'requires':['author.world4.area1.stage1']}
        fragment={'owner':'m','raw':{'worlds':[{'key':'m.w','title':'W','areas':[{'key':'m.w.a','title':'A','stages':[stage]}]}]},'assets':{},'visible':set()}
        with tempfile.TemporaryDirectory() as temp:
            (Path(temp)/'catalog.json').write_text(json.dumps(body),encoding='utf-8')
            catalog=Catalog(temp,units,[fragment])
            self.assertEqual(list(catalog.worlds)[-1],'m.w');self.assertEqual(catalog.owner['m.w.a.s'],'m')
            bad=json.loads(json.dumps(fragment['raw']));bad['worlds'][0]['key']='other.w'
            with self.assertRaises(ValueError):Catalog(temp,units,[dict(fragment,raw=bad)])
            hidden={'owner':'n','raw':{'worlds':[{'key':'n.w','title':'W','areas':[{'key':'n.w.a','title':'A','stages':[dict(stage,key='n.w.a.s',requires=['m.w.a.s'])]}]}]},'assets':{},'visible':set()}
            with self.assertRaises(ValueError):Catalog(temp,units,[fragment,hidden])
            self.assertIn('n.w',Catalog(temp,units,[fragment,dict(hidden,visible={'m'})]).worlds)
    def test_stage_music_sound_key(self):
        # 自定义音效（M6）：关卡 music 可写已登记且可见的 bgm 音效键。
        units=load_manifest(ROOT/'community_content')[0]['units']
        body=json.loads((ROOT/'campaign_content/catalog.example.json').read_text(encoding='utf-8'))
        stage={'key':'m.w.a.s','title':'S','scene':0,'music':'m.theme','enemies':[{'unit':3}],'waves':[{'tick':0,'enemy':0}]}
        fragment={'owner':'m','raw':{'worlds':[{'key':'m.w','title':'W','areas':[{'key':'m.w.a','title':'A','stages':[stage]}]}]},'assets':{},'visible':set()}
        with tempfile.TemporaryDirectory() as temp:
            (Path(temp)/'catalog.json').write_text(json.dumps(body),encoding='utf-8')
            self.assertIn('m.w.a.s',Catalog(temp,units,[fragment],sounds={'m.theme':'bgm'}).stages)
            for sounds in ({},{'m.theme':'se'},{'x.theme':'bgm'}):
                with self.assertRaises(ValueError):Catalog(temp,units,[json.loads(json.dumps(fragment,default=list))],sounds=sounds)

class NetworkTests(unittest.TestCase):
    def setUp(self):
        self.hash='a'*64;self.server=RoomServer(('127.0.0.1',0),self.hash,'fixture-secret')
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start();self.clients=[]
    def tearDown(self):
        for client in self.clients:client.close()
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=2)
    def client(self,content=None):
        c=OnlineClient(content or self.hash);self.clients.append(c)
        c.connect('127.0.0.1',self.server.server_address[1],'fixture-secret',tls=False);return c
    def messages(self,client,kind):
        limit=time.monotonic()+2
        while time.monotonic()<limit:
            found=[m for m in client.poll() if m.get('type')==kind]
            if found:return found
            time.sleep(.01)
        self.fail('协议响应超时：'+kind)
    def test_coop_and_community_id(self):
        a=self.client();b=self.client();a.join('test','coop');self.messages(a,'room');b.join('test','coop')
        room=self.messages(b,'room')[0];self.assertEqual(len(room['participants']),2)
        a.input(10,'deploy',unit_id=1029,unit_key='s1xlv.girida_o_mk2',slot=0)
        message=self.messages(b,'input')[0];self.assertEqual(message['unit_id'],1029);self.assertEqual(message['sequence'],0)
        units=[{'unit_id':1029,'unit_key':'s1xlv.girida_o_mk2','instance_id':1,'team':0,'hp':6300,'x':100.0,'y':338.0}]
        a.snapshot(11,units);snapshot=self.messages(b,'snapshot')[0];self.assertEqual(snapshot['state_hash'],validate_snapshot(snapshot))
    def test_pvp_and_capacity(self):
        clients=[self.client() for _ in range(3)]
        for c in clients[:2]:c.join('versus','pvp');self.messages(c,'room')
        clients[2].join('versus','pvp');self.assertEqual(self.messages(clients[2],'rejected')[0]['type'],'rejected')
    def test_version_mismatch(self):
        with self.assertRaises(ValueError):self.client('b'*64)
    def test_authentication_rejection(self):
        c=OnlineClient(self.hash);self.clients.append(c)
        with self.assertRaises(ValueError):c.connect('127.0.0.1',self.server.server_address[1],'incorrect-fixture-token',tls=False)
    def test_malformed_snapshot_rejected(self):
        a=self.client();a.join('invalid_state','coop');self.messages(a,'room')
        a.send({'type':'snapshot','frame':1,'units':[None],'state_hash':'a'*64})
        self.assertEqual(self.messages(a,'rejected')[0]['type'],'rejected')
    def test_external_tls_requirement(self):
        c=OnlineClient(self.hash)
        with self.assertRaises(ValueError):c.connect('192.0.2.1',14620,'fixture-secret',tls=False)

if __name__=='__main__':unittest.main(verbosity=2)
