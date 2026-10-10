"""Compile generated C++ to a Windows x64 DLL with existing local MinGW."""
from pathlib import Path
import subprocess,concurrent.futures,json,time,hashlib,sys,argparse
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
COMPILER=Path(r'C:\Program Files\mingw64\bin\g++.exe')
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library',default='msd_aot.dll',help='Output DLL basename; a distinct filename supports updating a running installation')
    parser.add_argument('--no-activate',action='store_true',help='Build without replacing the active core configuration')
    parser.add_argument('--no-sha256',action='store_true',help='Build without calculating SHA-256 or writing a digest')
    args=parser.parse_args();name=args.library
    if Path(name).name!=name or not name.lower().endswith('.dll'):raise ValueError('Invalid native DLL basename')
    out=ROOT/'build';out.mkdir(exist_ok=True)
    if not (ROOT/'community_blocks.inc').is_file():
        raise FileNotFoundError('The generated community_blocks.inc snapshot is required')
    # 行为库清单（模组 M2）：behavior_library.json 原文嵌入核心，由 msd_behavior_manifest 导出供加载器核对。
    library=(ROOT/'behavior_library.json').read_text(encoding='utf-8')
    json.loads(library)
    if ')MSD"' in library:raise ValueError('behavior_library.json contains the raw-string delimiter')
    manifest_inc=ROOT/'behavior_manifest.inc';generated='static const char BEHAVIOR_MANIFEST[]=R"MSD('+library+')MSD";\n'
    if not manifest_inc.is_file() or manifest_inc.read_text(encoding='utf-8')!=generated:manifest_inc.write_text(generated,encoding='utf-8')
    sources=[ROOT/'aot_runtime.cpp',ROOT/'native_imports.cpp',ROOT/'native_audio.cpp',ROOT/'generated/dispatch.cpp',*sorted((ROOT/'generated').glob('blocks_*.cpp')),ROOT/'community_content.cpp',ROOT/'event_trial_hooks.cpp',ROOT/'audio_options.cpp',ROOT/'lab_hooks.cpp',ROOT/'netplay.cpp']
    started=time.perf_counter()
    def compile_one(src):
        obj=out/(src.stem+'.o');log=out/(src.stem+'.log')
        dependencies=[src,ROOT/'aot_runtime.h']
        if src.parent==ROOT:dependencies.extend([ROOT/'native_imports.h',ROOT/'netplay.h'])
        if src.name=='native_audio.cpp':dependencies.append(ROOT/'third_party/stb_vorbis.c')
        if src.name=='community_content.cpp':dependencies.extend([ROOT/'community_blocks.inc',ROOT/'unit_level_rules.inc',ROOT/'behavior_manifest.inc'])
        if obj.exists() and obj.stat().st_mtime>max(p.stat().st_mtime for p in dependencies):return obj
        command=[str(COMPILER),'-std=c++17','-O2','-Wa,-mbig-obj','-fno-strict-aliasing','-ffp-contract=off','-fno-exceptions','-fno-rtti','-c',str(src),'-o',str(obj)]
        result=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
        log.write_text(result.stdout,encoding='utf-8')
        if result.returncode:
            obj.unlink(missing_ok=True)
            raise RuntimeError(str(log)+'\n'+result.stdout[:1800])
        print('compiled',src.name,flush=True);return obj
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:objects=list(pool.map(compile_one,sources))
    library=out/name
    command=[str(COMPILER),'-shared','-static-libgcc','-static-libstdc++','-o',str(library),*[str(p) for p in objects]]
    subprocess.run(command,check=True)
    result={'compiler':str(COMPILER),'target':'Windows x64 PE DLL','library':name,'seconds':time.perf_counter()-started,'bytes':library.stat().st_size,'objects':len(objects)}
    if not args.no_sha256:result['sha256']=hashlib.sha256(library.read_bytes()).hexdigest()
    (out/'build_result.json').write_text(json.dumps(result,indent=2))
    if not args.no_activate:(ROOT/'core_runtime.json').write_text(json.dumps({'library':name,**({'sha256':result['sha256']} if 'sha256' in result else {})},indent=2),encoding='utf-8')
    print(json.dumps(result))
if __name__=='__main__':main()
