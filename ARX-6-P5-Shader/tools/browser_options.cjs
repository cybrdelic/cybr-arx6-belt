/* Default Playwright browser is portable; optional local browser is explicit. */
const fs=require('fs');
function browserOptions(){
 const options={headless:true,args:['--enable-webgl','--ignore-gpu-blocklist']};
 if(process.env.ARX_CHROME){
  if(!fs.existsSync(process.env.ARX_CHROME))throw Error('ARX_CHROME does not exist');
  options.executablePath=process.env.ARX_CHROME;
 }
 if(process.env.ARX_ANGLE)options.args.push('--use-gl=angle','--use-angle='+process.env.ARX_ANGLE);
 return options;
}
module.exports={browserOptions};
