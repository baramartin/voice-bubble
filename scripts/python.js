// Runs a Python script with the right interpreter name for this OS ("python" on Windows, "python3" elsewhere).
// Used by the npm scripts: node scripts/python.js setup_wizard.py
const { spawnSync } = require('child_process');

const python = process.platform === 'win32' ? 'python' : 'python3';
const result = spawnSync(python, process.argv.slice(2), { stdio: 'inherit' });

if (result.error) {
  console.error(`Could not run "${python}". Install Python 3.10+ and make sure it is on your PATH.`);
  process.exit(1);
}
process.exit(result.status ?? 1);
