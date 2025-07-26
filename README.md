<div>

# buildozer编译环境搭建

pip install pyjnius cython==0.29.37 kivy plyer buildozer -i https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple/

sudo apt-get update

sudo apt-get install autoconf automake libtool pkg-config make gcc unzip

sudo apt-get install android-sdk openjdk-17-jdk sdkmanager


# 安装SDK cmdline-tools:

cd $HOME/Android/Sdk

wget https://dl.google.com/android/repository/commandlinetools-linux-9477386_latest.zip

unzip commandlinetools-linux-9477386_latest.zip

cp -r cmdline-tools tools


# 设置 ANDROID_SDK_ROOT 环境变量。编辑你的 ~/.bashrc 文件，添加以下行：

export ANDROID_SDK_ROOT=$HOME/Android/Sdk
export PATH=$PATH:$ANDROID_SDK_ROOT/tools:$ANDROID_SDK_ROOT/platform-tools


# 运行以下命令使环境生效：

source ~/.bashrc


# 使用 SDK Manager 安装所需的 SDK 组件和平台工具。运行以下命令启动 SDK Manager：

sdkmanager --install "platform-tools" "build-tools;latest" "platforms;android-31"
sdkmanager "build-tools;31.0.0"
sdkmanager "ndk;25.0.8775105"


如果sdkmanage 安装报错ANDROID_SDK_ROOT路径无效，请在命令后面添加--sdk_root=$HOME/Android/Sdk


# 导入路径:

echo 'export ANDROID_HOME=$HOME/Android/Sdk' >> ~/.bashrc
echo 'export PATH=$PATH:$ANDROID_HOME/emulator:$ANDROID_HOME/tools:$ANDROID_HOME/tools/bin:$ANDROID_HOME/platform-tools:$ANDROID_HOME/build-tools/31.0.0' >> ~/.bashrc
echo 'export ANDROIDNDK=$HOME/Android/Sdk/ndk/25.0.8775105' >> ~/.bashrc


# 运行以下命令使环境生效：

source ~/.bashrc


# 打包生成的 APK 文件：
buildozer -v android debug

# 重构编译命令:
buildozer android clean

buildozer android debug
</div>
