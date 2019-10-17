from setuptools import find_packages, setup


setup(
    name='nextbus',
    version='0.9.1',
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
        'sqlalchemy',
        'requests',
        'werkzeug',
        'wtforms'
    ],
    tests_require=[
        'pytest'
    ],
    entry_points={
        'console_scripts': ['nxb=nextbus.commands:cli']
    }
)
