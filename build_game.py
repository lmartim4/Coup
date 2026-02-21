import PyInstaller.__main__
import shutil
import os
import zipfile
import tarfile
import platform

# ================= CONFIGURAÇÕES =================
GAME_SCRIPT = "coup_game.py"  # Nome do seu script principal
APP_NAME = "CoupGame"         # Nome do executável final
VERSION = "v1.0.0"            # Mude isso a cada atualização!
OUTPUT_DIR = "build_output"   # Onde os arquivos finais ficarão
ASSETS_DIR = "assets"         # Pasta de imagens/sons (se tiver, deixe None se não tiver)
# =================================================

def clean_folders():
    """Limpa pastas de builds anteriores para evitar conflitos."""
    folders = ["dist", "build", OUTPUT_DIR]
    for folder in folders:
        if os.path.exists(folder):
            shutil.rmtree(folder)
            print(f"Limpeza: Pasta '{folder}' removida.")

def compile_game():
    """Usa o PyInstaller para gerar o executável."""
    print(f"Compilando {GAME_SCRIPT}...")
    
    os_name = platform.system()
    sep = ";" if os_name == "Windows" else ":"
    
    # Comandos básicos do PyInstaller
    args = [
        GAME_SCRIPT,
        '--name=%s' % APP_NAME,
        '--onedir',  # Cria uma pasta (melhor para atualizações do que um único arquivo gigante)
        '--clean',
        '--noconsole',  # Remove a tela preta (ative se precisar debugar erros)
    ]

    # Se tiver assets, inclui no comando
    if ASSETS_DIR and os.path.exists(ASSETS_DIR):
        args.append(f'--add-data={ASSETS_DIR}{sep}{ASSETS_DIR}')

    PyInstaller.__main__.run(args)
    print("Compilação concluída!")

def create_version_file():
    """Cria o arquivo version.txt dentro da pasta compilada."""
    # O launcher precisa desse arquivo para saber a versão instalada
    dist_folder = os.path.join("dist", APP_NAME)
    with open(os.path.join(dist_folder, "version.txt"), "w") as f:
        f.write(VERSION)
    print(f"Arquivo de versão ({VERSION}) criado.")

def package_release():
    """Compacta a pasta do jogo em .zip ou .tar.gz para o GitHub."""
    os_name = platform.system()
    dist_folder = os.path.join("dist", APP_NAME)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if os_name == "Windows":
        archive_name = f"{APP_NAME}-Windows-{VERSION}.zip"
        archive_path = os.path.join(OUTPUT_DIR, archive_name)
        
        print(f"Criando ZIP para Windows: {archive_name}")
        with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(dist_folder):
                for file in files:
                    file_path = os.path.join(root, file)
                    # Salva no zip mantendo a estrutura interna correta
                    arcname = os.path.relpath(file_path, start="dist")
                    zipf.write(file_path, arcname)

    elif os_name == "Linux":
        archive_name = f"{APP_NAME}-Linux-{VERSION}.tar.gz"
        archive_path = os.path.join(OUTPUT_DIR, archive_name)
        
        print(f"Criando TAR.GZ para Linux: {archive_name}")
        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add(dist_folder, arcname=APP_NAME)

    print(f"Release pronta em: {archive_path}")

if __name__ == "__main__":
    # Garante que tem o PyInstaller instalado
    try:
        import PyInstaller
    except ImportError:
        print("Erro: PyInstaller não encontrado. Rode 'pip install pyinstaller'.")
        exit()

    clean_folders()
    compile_game()
    create_version_file()
    package_release()