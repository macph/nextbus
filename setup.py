from setuptools import setup


setup(
    name='nextbus',
    version='0.1.0',
    packages=['nextbus'],
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
        'python-dateutil',
        'pytz',
        'requests'
    ],
    entry_points={
        'console_scripts': ['nxb=nextbus.commands:cli']
    }
)
