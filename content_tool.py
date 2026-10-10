"""扩展资源导入、内容核验与联机内容指纹工具。"""
from pathlib import Path
import sys,argparse,json,shutil
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT));import portable_launcher
from campaign_catalog import Catalog
from content_assets import import_png

def main():
    parser=argparse.ArgumentParser(description=__doc__);commands=parser.add_subparsers(dest='command',required=True)
    validate=commands.add_parser('validate');validate.add_argument('--catalog',type=Path,default=ROOT/'campaign_content');validate.add_argument('--mods',type=Path,default=ROOT/'mods');validate.add_argument('--enable',nargs='*',default=None)
    png=commands.add_parser('import-png');png.add_argument('source',type=Path);png.add_argument('destination',type=Path)
    music=commands.add_parser('import-music');music.add_argument('source',type=Path);music.add_argument('destination',type=Path)
    sample=commands.add_parser('install-example');sample.add_argument('--destination',type=Path,default=ROOT/'campaign_content/catalog.json')
    behaviors_cmd=commands.add_parser('list-behaviors');behaviors_cmd.add_argument('--markdown',type=Path)
    mods_cmd=commands.add_parser('check-mods');mods_cmd.add_argument('--mods',type=Path,default=ROOT/'mods');mods_cmd.add_argument('--enable',nargs='*',default=None)
    args=parser.parse_args()
    if args.command=='check-mods':
        # 离线校验模组目录（临时 ID 映射，不写存档与用户目录）；--enable 省略时启用目录中的全部模组（按文件夹名排序）。
        import os,tempfile,community_content as cc,content_ids,mod_loader
        os.environ['MSD_MODS_DIR']=str(args.mods)
        manifest,_,mods_range=cc.load_manifest(ROOT/'community_content')
        enabled=args.enable if args.enable is not None else [json.loads((d/'mod.json').read_text(encoding='utf-8')).get('id') for d in sorted(args.mods.iterdir()) if (d/'mod.json').is_file() and d.is_dir()] if args.mods.is_dir() else []
        with tempfile.TemporaryDirectory() as temp:
            id_map=content_ids.ModIdMap(Path(temp)/'ids.json',mods_range)
            units,assets,patches,status=mod_loader.load(ROOT,{u['key']:u for u in manifest['units']},enabled=[e for e in enabled if isinstance(e,str)],game_version=__import__('branding').load(ROOT)['display_version'],id_map=id_map,stock_assets=cc.stock_asset_exists,body_assets=set(manifest['assets']),body_root=ROOT/'community_content',stock_root=cc.stock_dir(),body_sounds={e['key']:e.get('type','se') for e in manifest.get('sounds',[])})
        print(json.dumps({'mods':status,'units':[{'key':u['key'],'id':u['id']} for u in units],'patches':patches},ensure_ascii=False,indent=2));return
    if args.command=='list-behaviors':
        import behaviors;library=behaviors.load_library()
        if args.markdown:args.markdown.write_text(behaviors.markdown(library)+'\n',encoding='utf-8',newline='\n');return
        print(behaviors.describe(library));return
    if args.command=='import-png':print(json.dumps(import_png(args.source,args.destination),ensure_ascii=False,indent=2));return
    if args.command=='install-example':
        if args.destination.exists() and json.loads(args.destination.read_text(encoding='utf-8')).get('worlds'):raise ValueError('目标已包含世界配置')
        args.destination.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/'campaign_content/catalog.example.json',args.destination);return
    if args.command=='import-music':
        if args.destination.suffix.lower()!='.msdf':raise ValueError('音乐输出扩展名应为 .msdf')
        raw=args.source.read_bytes()
        if not raw.startswith(b'OggS') or len(raw)>64*1024*1024:raise ValueError('音乐输入要求 Ogg Vorbis')
        import ctypes as C,static_cpu
        lib=static_cpu.Uc().lib;fn=lib.msd_vorbis_decode;fn.argtypes=[C.c_void_p,C.c_int32,C.POINTER(C.c_int32),C.POINTER(C.c_int32),C.POINTER(C.c_void_p)];fn.restype=C.c_int32
        channels=C.c_int32();rate=C.c_int32();pcm=C.c_void_p();frames=fn(raw,len(raw),C.byref(channels),C.byref(rate),C.byref(pcm))
        if frames<1:raise ValueError('音乐完整解码核验失败')
        free=lib.msd_vorbis_free;free.argtypes=[C.c_void_p];free(pcm)
        args.destination.parent.mkdir(parents=True,exist_ok=True);args.destination.write_bytes(raw)
        print(json.dumps({'file':args.destination.name,'blake2b':__import__('content_digest').blake2(raw),'channels':channels.value,'rate':rate.value,'frames':frames}));return
    # 本体世界目录与已启用模组片段（--mods/--enable 同 check-mods；缺省只校验本体）。
    import community_content as cc,content_ids,mod_loader,os,tempfile
    manifest,_,mods_range=cc.load_manifest(ROOT/'community_content')
    fragments=[];mod_units=[];sounds=[]
    if args.enable:
        os.environ['MSD_MODS_DIR']=str(args.mods)
        with tempfile.TemporaryDirectory() as temp:
            mod_units,_,_,status=mod_loader.load(ROOT,{u['key']:u for u in manifest['units']},enabled=args.enable,game_version=__import__('branding').load(ROOT)['display_version'],id_map=content_ids.ModIdMap(Path(temp)/'ids.json',mods_range),stock_assets=cc.stock_asset_exists,body_assets=set(manifest['assets']),body_root=ROOT/'community_content',stock_root=cc.stock_dir(),campaign_root=args.catalog,campaigns=fragments,sounds=sounds,body_sounds={e['key']:e.get('type','se') for e in manifest.get('sounds',[])})
        skipped=[s for s in status if s['state'] not in ('loaded','disabled')]
        if skipped:print(json.dumps({'skipped':skipped},ensure_ascii=False,indent=2))
    # 关卡 music 可写 bgm 音效键（M6）：本体 content.json 的 sounds 与已载入模组的音效。
    known={e['key']:e.get('type','se') for e in manifest.get('sounds',[])+sounds}
    catalog=Catalog(args.catalog,manifest['units']+mod_units,fragments,sounds=known)
    print(json.dumps({'worlds':len(catalog.worlds),'stages':len(catalog.stages),'scenes':len(catalog.scenes),'music':len(catalog.music),'sounds':len(known),'mods':[f['owner'] for f in fragments],'content_digest':catalog.fingerprint},indent=2))
if __name__=='__main__':main()
