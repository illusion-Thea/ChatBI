"""Run the built internal platform without the development Vite server."""
from pathlib import Path
import argparse
import sys

ROOT=Path(__file__).resolve().parent
packages=ROOT/'.venv/Lib/site-packages'
if packages.exists(): sys.path.insert(0,str(packages))
sys.path.insert(0,str(ROOT))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description='QueryX 内部数据平台')
    parser.add_argument('--port',type=int,default=8012)
    args=parser.parse_args()
    if not (ROOT/'frontend-vben/apps/web-business/dist/index.html').exists():
        raise SystemExit('请先执行 npm run build:business')
    print('管理员初始凭据（仅首次创建时生成）：'+str(ROOT/'.runtime/platform/initial-admin.txt'))
    import uvicorn
    uvicorn.run('commercial.main:app',host='127.0.0.1',port=args.port,app_dir=str(ROOT))
