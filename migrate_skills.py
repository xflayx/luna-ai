# migrate_skills.py - Script de Migração Automática de Skills

import os
import re

# Metadados para cada skill
SKILL_METADATA = {
    "atalhos_radial": {
        "nome": "Atalhos Radial",
        "descricao": "Abre menu radial de atalhos",
        "versao": "1.0.0",
        "autor": "Luna Team",
        "intents": ["atalhos_radial"]
    },
    "game_guide": {
        "nome": "Game Guide",
        "descricao": "Busca guias e tutoriais de jogos",
        "versao": "1.0.0",
        "autor": "Luna Team",
        "intents": ["game_guide"]
    },
    "macros": {
        "nome": "Macros (Deprecated)",
        "descricao": "Sistema antigo de macros - usar sequencia_manager",
        "versao": "1.0.0",
        "autor": "Luna Team",
        "intents": ["macros"]
    },
    "news": {
        "nome": "Notícias",
        "descricao": "Busca notícias usando SerpAPI",
        "versao": "1.0.0",
        "autor": "Luna Team",
        "intents": ["noticias", "news"]
    },
    "price": {
        "nome": "Price",
        "descricao": "Consulta preços de criptomoedas",
        "versao": "1.0.0",
        "autor": "Luna Team",
        "intents": ["preco", "price"]
    },
    "system_monitor": {
        "nome": "System Monitor",
        "descricao": "Monitora CPU, RAM e desempenho do sistema",
        "versao": "1.0.0",
        "autor": "Luna Team",
        "intents": ["system_monitor"]
    },
    "vision": {
        "nome": "Vision",
        "descricao": "Analisa imagens da tela usando Gemini Vision",
        "versao": "1.0.0",
        "autor": "Luna Team",
        "intents": ["visao", "vision"]
    },
    "web_reader": {
        "nome": "Web Reader",
        "descricao": "Lê e resume sites usando Playwright",
        "versao": "1.0.0",
        "autor": "Luna Team",
        "intents": ["web_reader"]
    }
}


def adicionar_skill_info(conteudo: str, nome_arquivo: str) -> str:
    """Adiciona SKILL_INFO no início do arquivo se não existir"""
    
    # Se já tem SKILL_INFO, não adiciona
    if "SKILL_INFO" in conteudo:
        return conteudo
    
    # Pega metadados
    nome_base = nome_arquivo.replace(".py", "")
    metadata = SKILL_METADATA.get(nome_base, {
        "nome": nome_base.title(),
        "descricao": "Skill sem descrição",
        "versao": "1.0.0",
        "autor": "Luna Team",
        "intents": [nome_base]
    })
    
    # Monta o bloco SKILL_INFO
    skill_info_block = f'''
# ========================================
# METADADOS DA SKILL (Padrão de Plugin)
# ========================================

SKILL_INFO = {{
    "nome": "{metadata['nome']}",
    "descricao": "{metadata['descricao']}",
    "versao": "{metadata['versao']}",
    "autor": "{metadata['autor']}",
    "intents": {metadata['intents']}
}}

'''
    
    # Encontra onde inserir (depois dos imports, antes de GATILHOS)
    linhas = conteudo.split('\n')
    
    # Procura a última linha de import
    ultimo_import = 0
    for i, linha in enumerate(linhas):
        if linha.strip().startswith('import ') or linha.strip().startswith('from '):
            ultimo_import = i
    
    # Insere depois dos imports
    linhas.insert(ultimo_import + 1, skill_info_block)
    
    return '\n'.join(linhas)


def adicionar_funcao_inicializar(conteudo: str, nome_skill: str) -> str:
    """Adiciona função inicializar() se não existir"""
    
    if "def inicializar()" in conteudo:
        return conteudo
    
    # Encontra onde adicionar (antes de executar())
    if "def executar(" not in conteudo:
        return conteudo
    
    init_block = f'''
# ========================================
# INICIALIZAÇÃO (Opcional)
# ========================================

def inicializar():
    """Chamada quando a skill é carregada"""
    print(f"✅ {{SKILL_INFO['nome']}} v{{SKILL_INFO['versao']}} inicializada")

'''
    
    # Insere antes de executar()
    conteudo = conteudo.replace(
        "def executar(",
        init_block + "def executar("
    )
    
    return conteudo


def migrar_skill(filepath: str) -> bool:
    """Migra uma skill individual"""
    
    print(f"\n🔄 Migrando: {os.path.basename(filepath)}")
    
    try:
        # Lê o arquivo
        with open(filepath, 'r', encoding='utf-8') as f:
            conteudo = f.read()
        
        # Backup
        backup_path = filepath + '.backup'
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(conteudo)
        print(f"   💾 Backup criado: {backup_path}")
        
        # Aplica migrações
        nome_arquivo = os.path.basename(filepath)
        conteudo_novo = conteudo
        
        # 1. Adiciona SKILL_INFO
        if "SKILL_INFO" not in conteudo:
            conteudo_novo = adicionar_skill_info(conteudo_novo, nome_arquivo)
            print("   ✅ SKILL_INFO adicionado")
        else:
            print("   ⏭️  SKILL_INFO já existe")
        
        # 2. Adiciona inicializar()
        if "def inicializar()" not in conteudo:
            conteudo_novo = adicionar_funcao_inicializar(conteudo_novo, nome_arquivo)
            print("   ✅ inicializar() adicionado")
        else:
            print("   ⏭️  inicializar() já existe")
        
        # 3. Verifica GATILHOS
        if "GATILHOS" not in conteudo:
            print("   ⚠️  GATILHOS não encontrados - ADICIONE MANUALMENTE!")
        else:
            print("   ✅ GATILHOS OK")
        
        # 4. Verifica executar()
        if "def executar(" not in conteudo:
            print("   ⚠️  executar() não encontrada - ADICIONE MANUALMENTE!")
        else:
            print("   ✅ executar() OK")
        
        # Salva o arquivo migrado
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(conteudo_novo)
        
        print(f"   💚 Migração concluída!")
        return True
        
    except Exception as e:
        print(f"   ❌ Erro: {e}")
        return False


def migrar_news_py(filepath: str) -> bool:
    """Migração especial para news.py que não tem estrutura padrão"""
    
    print(f"\n🔄 Migrando (especial): {os.path.basename(filepath)}")
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            conteudo = f.read()
        
        # Backup
        backup_path = filepath + '.backup'
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(conteudo)
        
        # Cria novo arquivo completo
        novo_conteudo = '''# skills/news.py
import requests
from config.settings import SERPAPI_API_KEY

# ========================================
# METADADOS DA SKILL (Padrão de Plugin)
# ========================================

SKILL_INFO = {
    "nome": "Notícias",
    "descricao": "Busca notícias usando SerpAPI",
    "versao": "1.0.0",
    "autor": "Luna Team",
    "intents": ["noticias", "news"]
}

# Gatilhos para esta skill
GATILHOS = ["notícia", "noticia", "news", "jornal", "acontecendo"]

# ========================================
# INICIALIZAÇÃO
# ========================================

def inicializar():
    """Chamada quando a skill é carregada"""
    print(f"✅ {SKILL_INFO['nome']} v{SKILL_INFO['versao']} inicializada")

# ========================================
# FUNÇÃO PRINCIPAL
# ========================================

def executar(comando: str) -> str:
    """Busca notícias baseado no comando"""
    
    # Remove palavras de ativação
    query = comando.replace("luna", "").replace("notícia", "").replace("sobre", "").strip()
    
    if not query:
        return "Quer notícias sobre o quê?"
    
    return buscar_noticias(query)

# ========================================
# FUNÇÕES AUXILIARES
# ========================================

def buscar_noticias(query: str) -> str:
    """Busca notícias usando SerpAPI"""
    
    params = {
        "engine": "google",
        "q": query,
        "hl": "pt-BR",
        "gl": "br",
        "api_key": SERPAPI_API_KEY
    }

    try:
        r = requests.get("https://serpapi.com/search", params=params, timeout=10)
        data = r.json()

        resultados = data.get("organic_results", [])[:3]
        if not resultados:
            return "Não encontrei informações relevantes sobre isso."

        titulos = " | ".join(r["title"] for r in resultados)
        return f"Encontrei isso: {titulos}"
        
    except Exception as e:
        return f"Erro ao buscar notícias: {str(e)}"
'''
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(novo_conteudo)
        
        print("   ✅ news.py totalmente reescrito")
        return True
        
    except Exception as e:
        print(f"   ❌ Erro: {e}")
        return False


def main():
    """Função principal"""
    
    print("=" * 60)
    print("🔧 SCRIPT DE MIGRAÇÃO DE SKILLS PARA PADRÃO DE PLUGINS")
    print("=" * 60)
    
    pasta_skills = "skills"
    
    if not os.path.exists(pasta_skills):
        print(f"❌ Pasta '{pasta_skills}' não encontrada!")
        return
    
    # Lista arquivos a migrar
    arquivos = [
        f for f in os.listdir(pasta_skills)
        if f.endswith('.py') and f != '__init__.py' and not f.startswith('_')
    ]
    
    print(f"\n📁 Encontrados {len(arquivos)} arquivos Python")
    print(f"📂 Pasta: {os.path.abspath(pasta_skills)}\n")
    
    # Mostra o que será migrado
    print("Arquivos a migrar:")
    for arq in arquivos:
        print(f"  • {arq}")
    
    print("\n" + "=" * 60)
    input("⚠️  Pressione ENTER para iniciar migração (ou Ctrl+C para cancelar)...")
    print("=" * 60)
    
    # Migra cada arquivo
    sucesso = 0
    falhas = 0
    
    for arquivo in arquivos:
        filepath = os.path.join(pasta_skills, arquivo)
        
        # Tratamento especial para arquivos problemáticos
        if arquivo == "news.py":
            resultado = migrar_news_py(filepath)
        else:
            resultado = migrar_skill(filepath)
        
        if resultado:
            sucesso += 1
        else:
            falhas += 1
    
    # Resumo
    print("\n" + "=" * 60)
    print("📊 RESUMO DA MIGRAÇÃO")
    print("=" * 60)
    print(f"✅ Sucesso: {sucesso}")
    print(f"❌ Falhas: {falhas}")
    print(f"📦 Total: {len(arquivos)}")
    print("=" * 60)
    
    print("\n💡 Próximos passos:")
    print("1. Verifique os arquivos .backup criados")
    print("2. Rode: python core/router.py")
    print("3. Veja se todas as skills foram carregadas")
    print("4. Teste: python test_system.py")
    print("\nSe algo der errado, restaure com os .backup!")


if __name__ == "__main__":
    main()