using System;
using System.ComponentModel;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Text;
using System.Text.RegularExpressions;
using System.Windows.Forms;
using Microsoft.Win32;

class Setup:Form {
 const string Version="0.1.0";
 const string DefaultId="__EXTENSION_ID__";
 const string Host="com.audioscribe.assistant";
 const string RegistryHost=@"Software\Google\Chrome\NativeMessagingHosts\com.audioscribe.assistant";
 const string RegistryUninstall=@"Software\Microsoft\Windows\CurrentVersion\Uninstall\AudioScribeAssistant";
 readonly string home=Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"AudioScribe");
 readonly bool zh=System.Globalization.CultureInfo.CurrentUICulture.Name.StartsWith("zh");
 Label notice;TextBox id;ProgressBar progress;Button install;CheckBox deleteData;bool completed=false;
 string T(string cn,string en){return zh?cn:en;}
 Setup(bool uninstall){
  Text=T("音频转文字 · 音频转写助手","AudioScribe Assistant");ClientSize=new Size(680,440);StartPosition=FormStartPosition.CenterScreen;FormBorderStyle=FormBorderStyle.FixedDialog;MaximizeBox=false;
  Font=new Font("Segoe UI",10);
  using(var logo=Assembly.GetExecutingAssembly().GetManifestResourceStream("logo.png"))if(logo!=null){var bitmap=new Bitmap(logo);Controls.Add(new PictureBox{Image=new Bitmap(bitmap),Location=new Point(25,20),Size=new Size(48,48),SizeMode=PictureBoxSizeMode.Zoom});bitmap.Dispose();}
  var title=new Label{Text=T("音频转文字 "+Version,"AudioScribe "+Version),Location=new Point(86,24),AutoSize=true,Font=new Font("Segoe UI",17,FontStyle.Bold)};Controls.Add(title);
  notice=new Label{Text=T("点击安装，自动安装助手和插件文件，无需手动解压。\n安装后按引导在 Chrome 确认加载。首次转写下载模型。","Install once. No separate Python installation or terminal needed.\nModels download on first use; models download as needed."),Location=new Point(25,70),Size=new Size(630,65)};Controls.Add(notice);
  Controls.Add(new Label{Text=T("自动安装到当前用户目录，与字幕插件独立。\n无需选择安装位置，也无需安装 Python。","Installs independently in your user profile.\nNo folder selection or separate Python installation needed."),Location=new Point(25,143),Size=new Size(630,55)});
  id=new TextBox{Text=DefaultId,Visible=false,ReadOnly=true};Controls.Add(id);
  progress=new ProgressBar{Location=new Point(25,211),Size=new Size(535,16)};Controls.Add(progress);
  install=new Button{Text=uninstall?T("卸载助手","Uninstall"):T("安装助手和插件","Install / update"),Location=new Point(375,248),Size=new Size(185,38)};Controls.Add(install);
  deleteData=new CheckBox{Text=T("同时删除识别模型和临时文件","Also delete models and temporary files"),Location=new Point(25,250),AutoSize=true,Visible=uninstall};Controls.Add(deleteData);
  install.Click+=(s,e)=>{
   if(completed){Close();return;}
   if(!uninstall&&!Regex.IsMatch(id.Text.Trim(),"^[a-p]{32}$")){MessageBox.Show(T("扩展 ID 需要 32 个 a–p 字母。","Extension ID must contain 32 letters a–p."));return;}
   install.Enabled=false;id.Enabled=false;
   var worker=new BackgroundWorker{WorkerReportsProgress=true};
   string extensionId=id.Text.Trim();bool erase=deleteData.Checked;
   worker.DoWork+=(a,b)=>{if(uninstall)Uninstall(erase);else Install(extensionId,worker);};
   worker.ProgressChanged+=(a,b)=>{progress.Value=Math.Min(100,b.ProgressPercentage);notice.Text=(string)b.UserState;};
   worker.RunWorkerCompleted+=(a,b)=>{
    if(b.Error!=null){notice.Text=T("操作失败：","Operation failed: ")+b.Error.Message;install.Enabled=true;id.Enabled=true;return;}
    progress.Value=100;notice.Text=uninstall?T("助手已卸载。请在 Chrome 中移除扩展。","Assistant removed. Remove the extension in Chrome."):T("文件安装完成。接下来需要在 Chrome 手动确认加载插件。\n点击下方按钮，按编号完成；以后点击插件图标即可打开。","Installed. Follow the steps below to load the extension in Chrome.\nThen click its icon to open AudioScribe.");
    if(!uninstall)ShowGuide();
    completed=true;install.Text=T("关闭","Close");install.Enabled=true;
   };worker.RunWorkerAsync();
  };
 }
 void ShowGuide(){
  string file=Path.Combine(home,"extension-path.txt");
  if(!File.Exists(file))return;
  string extension=File.ReadAllText(file).Trim();
  var path=new TextBox{Text=extension,ReadOnly=true,Location=new Point(25,300),Width=630};Controls.Add(path);
  var hint=new Label{Text=T("2. 在 Chrome 开启开发者模式 → 加载未打包的扩展程序\n3. 粘贴上方路径，按回车，再点‘选择文件夹’；不要进入 icons / _locales。","2. Enable Developer mode → Load unpacked in Chrome.\n3. Paste the path above, press Enter, then Select Folder."),Location=new Point(25,350),Size=new Size(630,60)};Controls.Add(hint);
  var open=new Button{Text=T("1. 复制路径并打开 Chrome","1. Copy path and open Chrome"),Location=new Point(25,248),Size=new Size(325,38)};Controls.Add(open);
  open.Click+=(s,e)=>{try{
   Clipboard.SetText(extension);
   string chrome=null;
   foreach(var hive in new[]{Registry.CurrentUser,Registry.LocalMachine})using(var key=hive.OpenSubKey(@"Software\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe")){if(key!=null)chrome=key.GetValue("") as string;if(chrome!=null)break;}
   if(chrome==null){foreach(string candidate in new[]{Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles),@"Google\Chrome\Application\chrome.exe"),Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86),@"Google\Chrome\Application\chrome.exe"),Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),@"Google\Chrome\Application\chrome.exe")})if(File.Exists(candidate)){chrome=candidate;break;}}
   if(chrome==null)throw new Exception(T("未找到 Chrome。路径已复制，请自行打开 chrome://extensions。","Chrome not found. Path copied; open chrome://extensions manually."));
   Process.Start(new ProcessStartInfo(chrome,"chrome://extensions/"){UseShellExecute=true});
  }catch(Exception ex){MessageBox.Show(ex.Message);}};
 }
 void ExtractExtension(){
  string target=Path.Combine(home,"Extensions","0.1.0-"+DateTime.Now.ToString("yyyyMMddHHmmssfff"));
  Directory.CreateDirectory(target);string prefix=Path.GetFullPath(target)+Path.DirectorySeparatorChar;
  using(var resource=Assembly.GetExecutingAssembly().GetManifestResourceStream("extension.zip")){
   if(resource==null)throw new Exception("Extension payload missing.");
   using(var zip=new ZipArchive(resource,ZipArchiveMode.Read))foreach(var entry in zip.Entries){
    string destination=Path.GetFullPath(Path.Combine(target,entry.FullName));
    if(!destination.StartsWith(prefix,StringComparison.OrdinalIgnoreCase))throw new Exception("Unsafe extension path.");
    if(entry.FullName.EndsWith("/")){Directory.CreateDirectory(destination);continue;}
    Directory.CreateDirectory(Path.GetDirectoryName(destination));entry.ExtractToFile(destination,true);
   }
  }
  if(!File.Exists(Path.Combine(target,"manifest.json")))throw new Exception("Extension manifest missing.");
  File.WriteAllText(Path.Combine(home,"extension-path.txt"),target,new UTF8Encoding(false));
 }
 void Install(string extensionId,BackgroundWorker worker){
  Directory.CreateDirectory(home);
  string app=Path.Combine(home,"app-"+Version);
  // Reinstallation must not overwrite an executable currently being used.
  if(Directory.Exists(app))app+="-"+DateTime.Now.ToString("yyyyMMddHHmmssfff");
  Directory.CreateDirectory(app);string prefix=Path.GetFullPath(app)+Path.DirectorySeparatorChar;
  using(Stream resource=Assembly.GetExecutingAssembly().GetManifestResourceStream("payload.zip")){
   if(resource==null)throw new Exception("Installer payload missing.");
   using(var zip=new ZipArchive(resource,ZipArchiveMode.Read)){
    long total=0,done=0;foreach(var entry in zip.Entries)total+=entry.Length;
    foreach(var entry in zip.Entries){
     string destination=Path.GetFullPath(Path.Combine(app,entry.FullName));
     if(!destination.StartsWith(prefix,StringComparison.OrdinalIgnoreCase))throw new Exception("Unsafe payload path.");
     if(entry.FullName.EndsWith("/")){Directory.CreateDirectory(destination);continue;}
     Directory.CreateDirectory(Path.GetDirectoryName(destination));entry.ExtractToFile(destination,true);done+=entry.Length;
     worker.ReportProgress((int)(done*80/Math.Max(1,total)),T("正在安装运行环境… ","Installing runtime… ")+done/1048576+" MB");
    }
   }
  }
  string executable=Path.Combine(app,"AudioScribeHost.exe");
  string manifest=Path.Combine(app,"native-host.json");
  string body="{\"name\":\""+Host+"\",\"description\":\"AudioScribe Assistant\",\"path\":\""+executable.Replace("\\","\\\\")+"\",\"type\":\"stdio\",\"allowed_origins\":[\"chrome-extension://"+extensionId+"/\"]}";
  File.WriteAllText(manifest,body,new UTF8Encoding(false));
  using(var key=Registry.CurrentUser.CreateSubKey(RegistryHost))key.SetValue("",manifest);
  string manager=Path.Combine(home,"AudioScribeMaintenance.exe");
  // Maintenance is a small executable, without an embedded installer payload.
  File.Copy(Path.Combine(app,"AudioScribeMaintenance.exe"),manager,true);
  using(var key=Registry.CurrentUser.CreateSubKey(RegistryUninstall)){
   key.SetValue("DisplayName","AudioScribe Assistant");key.SetValue("DisplayVersion",Version);
   key.SetValue("Publisher","AudioScribe");key.SetValue("UninstallString","\""+manager+"\" --uninstall");
   key.SetValue("InstallLocation",home);key.SetValue("NoModify",1);key.SetValue("NoRepair",1);
  }
  ExtractExtension();
  worker.ReportProgress(100,T("安装完成","Installed"));
 }
 static void CopyTree(string source,string target){
  Directory.CreateDirectory(target);
  foreach(string file in Directory.GetFiles(source))File.Copy(file,Path.Combine(target,Path.GetFileName(file)),false);
  foreach(string dir in Directory.GetDirectories(source)){
   if((File.GetAttributes(dir)&FileAttributes.ReparsePoint)!=0)continue;
   CopyTree(dir,Path.Combine(target,Path.GetFileName(dir)));
  }
 }
 void Uninstall(bool erase){
  string parent=Path.GetFullPath(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData))+Path.DirectorySeparatorChar;
  string resolved=Path.GetFullPath(home);
  if(!resolved.StartsWith(parent,StringComparison.OrdinalIgnoreCase)||Path.GetFileName(resolved)!="AudioScribe")throw new Exception("Unsafe uninstall target.");
  // Only remove this product's registration; never another product's registry keys.
  using(var key=Registry.CurrentUser.OpenSubKey(RegistryHost)){
   string registered=key==null?null:key.GetValue("") as string;
   if(registered!=null&&!Path.GetFullPath(registered).StartsWith(resolved+Path.DirectorySeparatorChar,StringComparison.OrdinalIgnoreCase))throw new Exception("Host registration points outside this installation.");
  }
  // User closes Chrome first. Never terminate unrelated processes.
  foreach(string dir in Directory.GetDirectories(home,"app-*")){
   if(!Path.GetFullPath(dir).StartsWith(resolved+Path.DirectorySeparatorChar,StringComparison.OrdinalIgnoreCase)||(File.GetAttributes(dir)&FileAttributes.ReparsePoint)!=0)throw new Exception("Unsafe application directory.");
   Directory.Delete(dir,true);
  }
  if(Directory.Exists(Path.Combine(home,"Data"))&&(File.GetAttributes(Path.Combine(home,"Data"))&FileAttributes.ReparsePoint)!=0)throw new Exception("Unsafe data directory.");
  if(erase&&Directory.Exists(Path.Combine(home,"Data")))Directory.Delete(Path.Combine(home,"Data"),true);
  Registry.CurrentUser.DeleteSubKeyTree(RegistryHost,false);Registry.CurrentUser.DeleteSubKeyTree(RegistryUninstall,false);
 }
 [STAThread]static void Main(string[] args){Application.EnableVisualStyles();Application.SetCompatibleTextRenderingDefault(false);bool guide=Array.IndexOf(args,"--guide")>=0;var form=new Setup(!guide&&(Array.IndexOf(args,"--uninstall")>=0||Assembly.GetExecutingAssembly().GetManifestResourceStream("payload.zip")==null));if(guide){form.completed=true;form.install.Text=form.T("关闭","Close");form.notice.Text=form.T("按下方步骤加载插件，完成后打开音频转文字。","Follow the steps below, then open AudioScribe.");form.ShowGuide();}Application.Run(form);}
}
