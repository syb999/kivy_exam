[app]
title = 测验生成器

package.name = quiz

package.domain = org.test

source.dir = .

android.window_soft_input_mode = adjustResize

source.include_exts = py,png,jpg,kv,atlas,db,ttf, json

source.include_patterns = *.py, assets/json/*.json, assets/font/*

source.include_dirs = assets, data

version = 1.1

requirements = python3, kivy, pyjnius,plyer, sdl2, sdl2_image, sdl2_ttf, sdl2_mixer, android, pillow, sqlite3, pandas, androidstorage4kivy

presplash.filename = %(source.dir)s/data/presplash.png

android.presplash_delay = 0
android.presplash_scale_type = centerCrop

icon.filename = %(source.dir)s/icons/icon.png

orientation = portrait

osx.python_version = 3

osx.kivy_version = 1.9.1

fullscreen = 0

android.permissions =  INTERNET, WRITE_EXTERNAL_STORAGE, READ_EXTERNAL_STORAGE, MANAGE_EXTERNAL_STORAGE

android.api = 30

android.minapi = 21

android.screen = tablet|large|normal

android.ndk_path = /home/oem/Android/Sdk/ndk/25.0.8775105

android.build_tools_version = 31.0.0

android.python = 3.9

android.arch = arm64-v8a

ios.kivy_ios_url = https://github.com/kivy/kivy-ios
ios.kivy_ios_branch = master

ios.ios_deploy_url = https://github.com/phonegap/ios-deploy
ios.ios_deploy_branch = 1.10.0

ios.codesign.allowed = false

[buildozer]
android.gradle_options = -Xmx2048m -XX:MaxPermSize=2048m
log_level = 2
