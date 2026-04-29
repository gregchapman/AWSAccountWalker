from setuptools import setup, find_packages

setup(
    name='AWSAccountWalker',
    version='0.1.1',
    packages=find_packages(),
    description='Python package for iterating AWS accounts and us regions via multithreading',
    author='Greg Chapman',
    author_email='greg.chapman@rackspace.com',
    keywords='Multithread AWS Organizations account visiting',
    install_requires=[
        'boto3>=1.21.28',  # Ensure you list all necessary packages here
    ],
)