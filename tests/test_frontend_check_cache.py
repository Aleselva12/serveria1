"""Run a real Vite configuration build with dependency/cache separation."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from updater.check_runner import run


ROOT = Path(__file__).resolve().parents[1]


class FrontendCacheTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node') and (ROOT/'frontend/node_modules/.bin/vite').exists(),
                         'Requires installed frontend dependencies and Node')
    def test_real_vite_build_keeps_generated_cache_outside_trusted_dependencies(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base/'source'; frontend = source/'frontend'; frontend.mkdir(parents=True)
            trusted = base/'trusted'; trusted.mkdir()
            output = base/'build'
            for name in ('package.json','package-lock.json'):
                shutil.copyfile(ROOT/'frontend'/name, frontend/name)
                shutil.copyfile(frontend/name, trusted/name)
            (trusted/'node_modules').symlink_to(ROOT/'frontend/node_modules', target_is_directory=True)
            (frontend/'tsconfig.json').write_text(json.dumps({'compilerOptions':{'skipLibCheck':True,'noEmit':True},'include':['main.ts']}))
            (frontend/'main.ts').write_text('document.body.textContent = "fixture";')
            (frontend/'index.html').write_text('<script type="module" src="/main.ts"></script>')
            (frontend/'vite.config.ts').write_text('import {defineConfig} from "vite"; export default defineConfig({});')
            captured = []
            def docker(*args):
                if args[0] == 'run':
                    script = args[-1].replace('/work/frontend', str(frontend)).replace('/opt/frontend', str(trusted)).replace('/tmp/project', str(output))
                    result = subprocess.run(['node','-e',script], capture_output=True, text=True, timeout=45)
                    captured.append(result)
                    return 'fixture-container'
                if args[0] == 'inspect': return 'false' if 'Running' in args[1] else str(captured[0].returncode)
                if args[0] == 'logs': return captured[0].stdout + captured[0].stderr
                if args[0] == 'rm': return ''
                raise AssertionError(args)
            result = run(source, ['frontend/tsconfig.json'], 'frontend_build', docker=docker)
            self.assertTrue(result['passed'], result['output'])
            self.assertTrue((output/'dist/index.html').is_file())
            self.assertFalse((output/'node_modules').is_symlink())
            self.assertTrue((output/'node_modules/.vite-temp').is_dir())
            self.assertFalse((output/'node_modules/.vite-temp').is_symlink())
            self.assertTrue((output/'node_modules/vite').is_symlink())


if __name__ == '__main__': unittest.main()
