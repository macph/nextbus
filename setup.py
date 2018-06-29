from setuptools import find_packages, setup


setup(
    name='nextbus',
    version='0.5.0',
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        'click',
        'flask',
        'flask_migrate',
        'flask_sqlalchemy',
        'flask_wtf',
        'lxml',
        'psycopg2',
        'pyparsing',
        'python-dateutil',
        'pytz',
        'sqlalchemy',
        'requests',
        'werkzeug',
        'wtforms'
    ],
    entry_points={
        'console_scripts': ['nxb=nextbus.commands:cli']
    }
)
