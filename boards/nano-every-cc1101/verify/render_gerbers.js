const fs = require('fs'), path = require('path'), stackup = require('pcb-stackup');
const dir = process.argv[2], tag = process.argv[3];
const files = fs.readdirSync(dir).filter(f => /\.(gtl|gbl|gts|gbs|gtp|gto|gbo|gm1|drl|gbr)$/i.test(f) && !/drl_map|job/.test(f));
const layers = files.map(f => ({filename: f, gerber: fs.createReadStream(path.join(dir, f))}));
stackup(layers).then(s => {
  fs.writeFileSync(`${tag}_top.svg`, s.top.svg); fs.writeFileSync(`${tag}_bottom.svg`, s.bottom.svg);
  const vb = x => x.svg.match(/viewBox="([^"]+)"/)[1];
  console.log(tag, 'top viewBox', vb(s.top), '| bottom viewBox', vb(s.bottom));
  for (const l of s.layers) console.log('  ', l.filename.padEnd(40), l.side, l.type, 'viewBox', l.converter.viewBox.map(v=>Math.round(v)/1000).join(' '));
}).catch(e => console.error('ERR', e.message));
