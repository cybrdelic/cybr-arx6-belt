/* Default Playwright browser is portable; optional local browser is explicit. */
const fs=require('fs');
function browserOptions(){
 const headless=process.env.ARX_HEADLESS;
 if(headless!==undefined&&!['0','1'].includes(headless))throw Error('ARX_HEADLESS must be 0 or 1');
 const options={headless:headless!=='0',args:['--enable-webgl','--ignore-gpu-blocklist']};
 if(process.env.ARX_BROWSER_LOG==='1')options.args.push('--enable-logging','--v=1');
 if(process.env.ARX_CHROME){
  if(!fs.existsSync(process.env.ARX_CHROME))throw Error('ARX_CHROME does not exist');
  options.executablePath=process.env.ARX_CHROME;
 }
 if(process.env.ARX_ANGLE)options.args.push('--use-gl=angle','--use-angle='+process.env.ARX_ANGLE);
 return options;
}
module.exports={browserOptions};
