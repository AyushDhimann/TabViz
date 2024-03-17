from setuptools import setup, find_packages

setup(
    name='tabvizz',
    version='1.2',
    packages=find_packages(),
    package_data={'tabvizz': ['static/*']},
    include_package_data=True,
    author='Ayush Dhiman',
    author_email='ayushdhiman272@gmail.com',
    description='Description of your package',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/AyushDhimann/tabvizz',
    license='MIT',
    install_requires=[
        'tableauserverclient',
        'tableau-api-lib',
        'google-generativeai'
    ],
)
