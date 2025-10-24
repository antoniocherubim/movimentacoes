import PyInstaller.__main__
import os
import shutil

def clean_dist():
    """Limpa diretórios de build anteriores"""
    dirs_to_clean = ['build', 'dist']
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)

def copy_config():
    """Copia o arquivo de configuração para o diretório dist"""
    if os.path.exists('config.ini'):
        shutil.copy2('config.ini', 'dist/config.ini')

def build():
    """Gera o executável usando PyInstaller"""
    print("Iniciando build do executável...")
    
    # Limpa builds anteriores
    clean_dist()
    
    # Configuração do PyInstaller
    PyInstaller.__main__.run([
        'main.py',                    # Script principal
        '--name=consulta_processos',  # Nome do executável
        '--onefile',                  # Gera um único arquivo
        '--add-data=eproc;eproc',    # Inclui o módulo eproc
        '--add-data=projudi_tjpr;projudi_tjpr',  # Inclui o módulo projudi
        '--hidden-import=PIL._tkinter_finder',  # Import necessário para o Pillow
        '--hidden-import=tkinter',    # Import necessário para o tkinter
    ])
    
    # Copia arquivo de configuração
    copy_config()
    
    # Cria diretório MEDIA se não existir
    os.makedirs('dist/MEDIA', exist_ok=True)
    
    print("Build concluído! O executável está disponível no diretório 'dist'")

if __name__ == '__main__':
    build() 