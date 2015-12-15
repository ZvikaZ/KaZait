# -*- mode: python -*-

block_cipher = None


a = Analysis(['kazait.py'],
             pathex=['c:\\Users\\zharamax\\PycharmProjects\\KaZait'],
             binaries=None,
             datas=None,
             hiddenimports=[],
             hookspath=None,
             runtime_hooks=None,
             excludes=None,
             win_no_prefer_redirects=None,
             win_private_assemblies=None,
             cipher=block_cipher)
	     
a.datas += [('main.glade', r'main.glade', 'DATA')]
a.datas += [('ffmpeg.exe', r'ffmpeg.exe', 'DATA')]
a.datas += [('gtkrc', r'C:\Python27\Lib\site-packages\gtk-2.0\runtime\share\themes\MS-Windows\gtk-2.0\gtkrc', 'DATA')]
a.binaries += [(r'lib\gtk-2.0\2.10.0\engines\libwimp.dll', r'C:\Python27\Lib\site-packages\gtk-2.0\runtime\lib\gtk-2.0\2.10.0\engines\libwimp.dll', 'BINARY') ]
a.binaries += [(r'share\locale\he\LC_MESSAGES\gtk20.mo', r'C:\Python27\Lib\site-packages\gtk-2.0\runtime\share\locale\he\LC_MESSAGES\gtk20.mo', 'BINARY') ]


pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          name='KaZait',
          debug=False,
          strip=None,
          upx=True,
          console=False,
          icon='Icons-Land-3d-Food-Fruit-Olive-Green.ico' )
