using System;
using System.Diagnostics;
using System.IO;
using System.Threading;

class Bridge {
 static void Pump(Stream input,Stream output){var buffer=new byte[16384];int count;while((count=input.Read(buffer,0,buffer.Length))>0){output.Write(buffer,0,count);output.Flush();}}
 static int Main(string[] args) {
  string app=AppDomain.CurrentDomain.BaseDirectory;
  var info=new ProcessStartInfo(Path.Combine(app,"runtime","python.exe"));
  info.Arguments="-I -u \""+Path.Combine(app,"native","host.py")+"\"";
  foreach(string arg in args) {
   if(arg.Contains("\"") || arg.Contains("\r") || arg.Contains("\n"))return 2;
   info.Arguments+=" \""+arg+"\"";
  }
  info.WorkingDirectory=app;info.UseShellExecute=false;info.CreateNoWindow=true;
  info.RedirectStandardInput=true;info.RedirectStandardOutput=true;info.RedirectStandardError=true;
  info.EnvironmentVariables.Remove("PYTHONPATH");info.EnvironmentVariables.Remove("PYTHONHOME");
  try {
   using(var child=Process.Start(info)) {
    var input=new Thread(()=>{try{Pump(Console.OpenStandardInput(),child.StandardInput.BaseStream);}catch{}finally{try{child.StandardInput.Close();}catch{}}});
    input.IsBackground=true;input.Start();
    var error=new Thread(()=>{try{Pump(child.StandardError.BaseStream,Console.OpenStandardError());}catch{}});
    error.IsBackground=true;error.Start();
    Pump(child.StandardOutput.BaseStream,Console.OpenStandardOutput());child.WaitForExit();return child.ExitCode;
   }
  }catch(Exception e){Console.Error.WriteLine(e.Message);return 1;}
 }
}
