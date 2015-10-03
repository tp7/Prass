from setuptools import setup

setup(
    name='Prass',
    version='0.1',
    py_modules=['prass', 'common', 'subs', 'tools'],
    install_requires=['Click'],
    entry_points='''
        [console_scripts]
        prass=prass:cli
    ''',
)
