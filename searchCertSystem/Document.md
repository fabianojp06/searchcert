\# Documento Consolidado: Sistema de Consulta de Certificações por IA (CertiBot)

\#\# 1\. Visão Geral do Produto  
O \*\*CertiBot\*\* é um sistema baseado em Inteligência Artificial desenvolvido para reduzir o tempo de resposta do setor de Recursos Humanos (RH) em consultas sobre certificações de colaboradores. Ele substitui buscas manuais em pastas ou planilhas por uma interface conversacional (chatbot) proprietária e interna, capaz de interpretar linguagem natural e retornar dados precisos e atualizados.

\---

\#\# 2\. Estrutura de Dados e Motor de Ingestão  
A fonte de dados principal do sistema são arquivos PDF armazenados no Google Drive. A estrutura de pastas definida segue o padrão: \*\*Pasta da Pessoa \> Pasta da Certificação \> Arquivo PDF\*\*.

\* \*\*Estratégia de Extração:\*\* A API do Google Drive fornecerá o Nome da pessoa e o Nome da Certificação diretamente pela leitura dos títulos das pastas, reduzindo drasticamente a dependência de IA para leitura de textos com layouts variáveis.  
\* \*\*Motor Invisível (Worker):\*\* Um script em Python rodará em background integrado aos Webhooks do Google Drive. Sempre que o RH adicionar um novo PDF, o sistema processará a extração de texto (focando apenas nas Datas de Emissão e Validade) e salvará no banco de dados automaticamente, de forma totalmente transparente ao usuário.

\---

\#\# 3\. Arquitetura e Stack de Desenvolvimento  
A solução adotada é 100% proprietária, garantindo controle total sobre a interface, a experiência do usuário e a segurança da informação:

\* \*\*Linguagem Principal (Backend e Worker):\*\* Python (ideal para orquestrar a IA, processar os PDFs e interagir com as APIs).  
\* \*\*Processamento de PDF:\*\* PyMuPDF ou pdfplumber.  
\* \*\*Banco de Dados & Backend (BaaS):\*\* Supabase (atuando como PostgreSQL hospedado para leitura e gravação rápida).  
\* \*\*Interface do Chatbot (Frontend):\*\* React.js (ou Next.js).  
\* \*\*API do Chatbot (Backend da Interface):\*\* FastAPI (Python) para comunicação de alta performance.  
\* \*\*Camada de IA (NLP):\*\* LangChain integrado a um LLM hospedado no backend, responsável por traduzir a linguagem natural para consultas no Supabase.

\---

\#\# 4\. Histórias de Usuário (User Stories) e Backlog Detalhado do MVP  
\[cite\_start\]O MVP foi quebrado em 3 grandes Épicos com suas respectivas Histórias de Usuário (US), Critérios de Aceite (CA) e tarefas técnicas para garantir uma entrega funcional\[cite: 1\].

\#\#\# 🗂️ ÉPICO 1: O Motor de Ingestão e Banco de Dados (Worker \+ Supabase)  
\[cite\_start\]\*\*Objetivo:\*\* Garantir que os dados saiam do Google Drive, sejam lidos e persistidos no banco de dados sem intervenção humana\[cite: 1\].

\[cite\_start\]\*\*US001 \- Criar Estrutura de Banco de Dados no Supabase\*\* \[cite: 1\]  
\* \[cite\_start\]\*\*COMO\*\* Arquiteto de Software, \*\*QUERO\*\* configurar o projeto no Supabase e criar o modelo relacional, \*\*PARA\*\* armazenar os dados dos colaboradores e suas certificações\[cite: 1\].  
\* \[cite\_start\]\*\*Critérios de Aceite (CA):\*\* \[cite: 1\]  
  \* \[cite\_start\]CA 1\. O projeto deve estar criado no ambiente do Supabase\[cite: 1\].  
  \* \[cite\_start\]CA 2\. Tabela \`colaboradores\` criada com: id (UUID), nome (String), link\_pasta (String)\[cite: 1\].  
  \* \[cite\_start\]CA 3\. Tabela \`certificacoes\` criada com: id (UUID), colaborador\_id (FK), nome\_certificado (String), data\_emissao (Date), data\_validade (Date), link\_pdf (String)\[cite: 1\].  
\* \[cite\_start\]\*\*Tarefas Técnicas:\*\* \[cite: 1\]  
  \* \[cite\_start\]\[ \] Gerar chaves de API (anon key e service\_role) do Supabase\[cite: 1\].  
  \* \[cite\_start\]\[ \] Escrever script SQL de criação das tabelas e relacionamentos\[cite: 1\].

\[cite\_start\]\*\*US002 \- Mapeamento de Pastas via API do Google Drive\*\* \[cite: 1\]  
\* \[cite\_start\]\*\*COMO\*\* Sistema Worker, \*\*QUERO\*\* me conectar à API do Google Drive e mapear a estrutura de pastas (Colaborador \> Certificação \> PDF), \*\*PARA\*\* identificar novos certificados ou atualizações\[cite: 1\].  
\* \[cite\_start\]\*\*Critérios de Aceite (CA):\*\* \[cite: 1\]  
  \* \[cite\_start\]CA 1\. Autenticação na API do Google via Conta de Serviço (Service Account)\[cite: 1\].  
  \* \[cite\_start\]CA 2\. O script deve listar os nomes das pastas "pai" (Colaboradores) e "filhas" (Certificações)\[cite: 1\].  
  \* \[cite\_start\]CA 3\. O script deve retornar a URL (link de visualização) do arquivo PDF encontrado\[cite: 1\].  
\* \[cite\_start\]\*\*Tarefas Técnicas:\*\* \[cite: 1\]  
  \* \[cite\_start\]\[ \] Configurar projeto no Google Cloud e gerar JSON da Service Account\[cite: 1\].  
  \* \[cite\_start\]\[ \] Desenvolver função Python para varrer as pastas e retornar um JSON estruturado\[cite: 1\].

\[cite\_start\]\*\*US003 \- Extração de Datas de Emissão e Validade (OCR/PDF)\*\* \[cite: 1\]  
\* \[cite\_start\]\*\*COMO\*\* Sistema Worker, \*\*QUERO\*\* ler o conteúdo interno dos PDFs mapeados, \*\*PARA\*\* extrair especificamente as datas de emissão e validade da certificação\[cite: 1\].  
\* \[cite\_start\]\*\*Critérios de Aceite (CA):\*\* \[cite: 1\]  
  \* \[cite\_start\]CA 1\. O sistema deve abrir o PDF em memória usando PyMuPDF ou pdfplumber\[cite: 1\].  
  \* \[cite\_start\]CA 2\. Deve utilizar Regex (Expressões Regulares) ou prompt leve de IA para localizar strings com formato de data próximas a palavras-chave (ex: "Emitido em", "Válido até")\[cite: 1\].  
  \* \[cite\_start\]CA 3\. O script deve enviar os dados consolidados via POST para a API do Supabase\[cite: 1\].

\#\#\# 🧠 ÉPICO 2: O Cérebro do Chatbot (Backend FastAPI \+ IA)  
\[cite\_start\]\*\*Objetivo:\*\* Receber perguntas em linguagem natural, traduzi-las e buscar a resposta correta no Supabase\[cite: 1\].

\[cite\_start\]\*\*US004 \- Criar API do Chatbot (FastAPI)\*\* \[cite: 1\]  
\* \[cite\_start\]\*\*COMO\*\* Desenvolvedor Backend, \*\*QUERO\*\* criar uma API REST em FastAPI, \*\*PARA\*\* servir de ponte entre a interface do usuário e o motor de Inteligência Artificial\[cite: 1\].  
\* \[cite\_start\]\*\*Critérios de Aceite (CA):\*\* \[cite: 1\]  
  \* \[cite\_start\]CA 1\. API deve possuir um endpoint \`POST /chat\` que recebe a mensagem do usuário\[cite: 1\].  
  \* \[cite\_start\]CA 2\. Retornar um JSON padronizado com a resposta do bot e a lista de links de evidência\[cite: 1\].

\[cite\_start\]\*\*US005 \- Orquestração de IA com LangChain (Text-to-SQL / Buscas)\*\* \[cite: 1\]  
\* \[cite\_start\]\*\*COMO\*\* Usuário do Chatbot, \*\*QUERO\*\* fazer perguntas de forma natural, \*\*PARA\*\* que a IA entenda minha intenção e filtre o banco de dados corretamente\[cite: 1\].  
\* \[cite\_start\]\*\*Critérios de Aceite (CA):\*\* \[cite: 1\]  
  \* \[cite\_start\]CA 1\. O LangChain deve receber a pergunta e identificar as entidades (Tecnologia/Certificação e Condição de Tempo)\[cite: 1\].  
  \* \[cite\_start\]CA 2\. A IA deve formatar a requisição para buscar na base do Supabase (ex: data\_validade \>= HOJE)\[cite: 1\].  
  \* \[cite\_start\]CA 3\. A resposta final gerada pelo LLM deve ser amigável, listando os nomes e incluindo o link do PDF\[cite: 1\].

\#\#\# 🎨 ÉPICO 3: A Interface Customizada (Frontend React)  
\[cite\_start\]\*\*Objetivo:\*\* Entregar uma tela de chat corporativa, limpa e responsiva para o RH\[cite: 1\].

\[cite\_start\]\*\*US006 \- Desenvolver Interface de Chat (UI/UX)\*\* \[cite: 1\]  
\* \[cite\_start\]\*\*COMO\*\* Analista de RH, \*\*QUERO\*\* acessar uma página web de chat intuitiva, \*\*PARA\*\* interagir com o bot sem precisar instalar novos aplicativos\[cite: 1\].  
\* \[cite\_start\]\*\*Critérios de Aceite (CA):\*\* \[cite: 1\]  
  \* \[cite\_start\]CA 1\. Layout deve conter uma área central de histórico de mensagens e um input de texto na parte inferior\[cite: 1\].  
  \* \[cite\_start\]CA 2\. Inclusão de indicador de "Digitando..." enquanto o backend processa a resposta\[cite: 1\].  
  \* \[cite\_start\]CA 3\. Mensagens do bot que contiverem links para o Drive devem ser renderizadas como "Cards" ou botões clicáveis\[cite: 1\].  
\* \[cite\_start\]\*\*Tarefas Técnicas:\*\* \[cite: 1\]  
  \* \[cite\_start\]\[ \] Criar projeto React.js ou Next.js\[cite: 1\].  
  \* \[cite\_start\]\[ \] Estilizar componentes de "Balão de Mensagem do Usuário" e "Balão de Mensagem do Bot"\[cite: 1\].  
  \* \[cite\_start\]\[ \] Integrar o input de texto para fazer a requisição HTTP POST \`/chat\` no backend FastAPI\[cite: 1\].

\---

\#\# 5\. Experiência do Usuário (UX/UI) e Fluxos

\#\#\# Interface e Interação  
O foco da aplicação web é oferecer "fricção zero". O Analista de RH poderá fazer perguntas abertas e o sistema fornecerá feedback visual ("Processando..." ou "Digitando...") durante a busca.  
\* \*\*O "Plus" da Interface:\*\* Além de retornar os dados estruturados, o bot sempre oferecerá um \*\*link direto e clicável\*\* para o PDF original no Google Drive, permitindo que o RH valide o documento com um único clique.

\#\#\# Exemplo de Resposta do Bot  
\* \*\*RH:\*\* "Quais as certificações ativas do João Silva?"  
\* \*\*Bot:\*\* \> 🤖 Encontrei as seguintes certificações:  
  \> 👤 \*\*João Silva\*\* possui a certificação Scrum Master (CSM).  
  \> 📅 Emissão: 15/01/2024 | Validade: 15/01/2026  
  \> 📄 \[Clique aqui para visualizar o certificado original\]

\---

\#\# 6\. Fluxo da Solução (Ponta a Ponta)

O funcionamento operacional do sistema segue 5 passos fundamentais:  
1\. \*\*Ingestão:\*\* O documento PDF é alocado na pasta correta no Google Drive (ex: \*João Silva / Scrum Master / certificado.pdf\*).  
2\. \*\*Processamento:\*\* O Worker em Python identifica o novo arquivo, lê o PDF, estrutura os dados e os salva silenciosamente no Supabase.  
3\. \*\*Acesso:\*\* O Analista de RH abre a página web interna do Chatbot proprietário.  
4\. \*\*Interação:\*\* O usuário envia uma pergunta em linguagem natural no chat.  
5\. \*\*Resposta:\*\* O Frontend envia a requisição para a API FastAPI. O LangChain interpreta a intenção, consulta as tabelas no Supabase em milissegundos e retorna os dados na interface web, acompanhados dos links originais do Google Drive.  


Supabase
Criação do banco

-- 1. Criação da tabela de Colaboradores
CREATE TABLE colaboradores (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    nome TEXT NOT NULL,
    link_pasta_drive TEXT,
    ativo BOOLEAN DEFAULT TRUE NOT NULL, -- Campo de status adicionado (True = Sim, False = Não)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 2. Criação da tabela de Certificações
CREATE TABLE certificacoes (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    colaborador_id UUID NOT NULL REFERENCES colaboradores(id) ON DELETE CASCADE,
    nome_certificado TEXT NOT NULL,
    data_emissao DATE,
    data_validade DATE,
    link_pdf TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 3. Criação de Índices para deixar o Chatbot ultra-rápido nas buscas
CREATE INDEX idx_colaboradores_ativo ON colaboradores(ativo); -- Novo índice para buscas rápidas por status!
CREATE INDEX idx_certificacoes_nome ON certificacoes(nome_certificado);
CREATE INDEX idx_certificacoes_validade ON certificacoes(data_validade);