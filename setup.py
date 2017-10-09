from setuptools import setup


setup(
    name='nextbus',
    packages=['nextbus'],
    include_package_data=True,
    install_requires=[
        'click',
        'flask',
        'flask_migrate',
        'flask_sqlalchemy',
        'flask_wtf',
        'lxml',
        'requests'
    ],
)
