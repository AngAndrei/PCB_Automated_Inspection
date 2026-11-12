import { createRequire } from 'node:module';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const require = createRequire(import.meta.url);
const cli = resolve(dirname(require.resolve('@playwright/test/package.json')), 'cli.js');
const browsers = resolve(dirname(fileURLToPath(import.meta.url)), '../../data/browsers');
const result = spawnSync(process.execPath, [cli, ...process.argv.slice(2)], {
  stdio: 'inherit', env: { ...process.env, PLAYWRIGHT_BROWSERS_PATH: browsers },
});
if (result.error) throw result.error;
process.exit(result.status ?? 1);
