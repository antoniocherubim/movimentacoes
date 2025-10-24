import pandas as pd

file1 = "C:/Users/Antonio/Desktop/Codes/WebScrapping/movimentacoes/processos_faltantes_filtrados.xlsx"
file2 = "C:/Users/Antonio/Desktop/Codes/WebScrapping/movimentacoes/movimentacoes_parcial_20250519_154204.xlsx"
file3 = "C:/Users/Antonio/Desktop/Codes/WebScrapping/movimentacoes/erros_parcial_tribunal_nao_suportado.xlsx"

df_1 = pd.read_excel(file1)
df_2 = pd.read_excel(file2)
df_3 = pd.read_excel(file3)

# Limpa pontos e traços do processo em df_2
df_2["processo"] = df_2["processo"].astype(str).str.replace(r"[.-]", "", regex=True)

# Garante que os processos estão em formato string
df_1["PROCESSO"] = df_1["PROCESSO"].astype(str)
df_3["Processo"] = df_3["Processo"].astype(str)

# Cria os conjuntos
set_processos = set(df_1["PROCESSO"])
set_processos_processados = set(df_2["processo"])
set_processados_erro = set(df_3["Processo"])

# Calcula processos faltantes
processos_faltantes = set_processos - set_processos_processados - set_processados_erro

# Filtra df_1 para manter apenas os processos faltantes
df_1_faltantes = df_1[df_1["PROCESSO"].isin(processos_faltantes)]

# (Opcional) Salvar em Excel
df_1_faltantes.to_excel("C:/Users/Antonio/Desktop/processos_faltantes_filtrados.xlsx", index=False)
