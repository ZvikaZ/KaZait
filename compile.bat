@echo off
rem # create Spec single file:
rem pyi-makespec -n KaZait -w -F kazait.py
rem # or, create Spec Dir mode:
rem pyi-makespec -n KaZait -w kazait.py

rem we might add '-i file.ico'

rem # After creating SPEC file it should be manually modified to include:
rem '
rem a.datas += [('main.glade', r'main.glade', 'DATA')]
rem a.datas += [('gtkrc', r'C:\Python27\Lib\site-packages\gtk-2.0\runtime\share\themes\MS-Windows\gtk-2.0\gtkrc', 'DATA')]
rem a.binaries += [(r'lib\gtk-2.0\2.10.0\engines\libwimp.dll', r'C:\Python27\Lib\site-packages\gtk-2.0\runtime\lib\gtk-2.0\2.10.0\engines\libwimp.dll', 'BINARY') ]
rem '
rem before 'pyz' section
rem
rem Actual Compiling the SPEC file
rem In order to support UPX (compressing the .EXE file by ~ 25%)
rem add this: '--upx-dir C:\Users\zharamax\Downloads\upx391w\upx391w'
rem
pyinstaller KaZait.spec
pause
