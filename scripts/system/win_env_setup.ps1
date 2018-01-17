
# Make sure to change ExecutionPolicy to RemoteSigned or Unristricted,
# or the script will not be executed.
# Set-ExecutionPolicy RemoteSigned


mkdir Tmp
cd Tmp


# Install talib library
(new-object System.Net.WebClient).DownloadFile("http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-msvc.zip","$((Resolve-Path .\).Path)\ta-lib-0.4.0-msvc.zip")
Expand-Archive "$((Resolve-Path .\).Path)\ta-lib-0.4.0-msvc.zip" -DestinationPath $((Resolve-Path .\).Path)
cp -R ta-lib "C:\ta-lib"


pip install -r ../../../requirements.txt


# Install matplotlib finance package
git clone https://github.com/matplotlib/mpl_finance.git
cd mpl_finance
python setup.py install


# Install Mongodb (manually)