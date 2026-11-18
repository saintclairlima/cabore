# Caboré

**API assíncrona de busca semântica e recomendação baseada em embeddings.**

Caboré é um serviço HTTP para organizar coleções vetoriais por aplicação (tenant), armazenar embeddings com metadados e consultar conteúdos semanticamente próximos a partir de texto. O projeto combina FastAPI, PostgreSQL, pgvector e modelos de embedding executados localmente por `sentence-transformers`.

> **Banco de dados:** a migration inicial `6fc3236d6e1c` habilita a extensão `vector` com `CREATE EXTENSION IF NOT EXISTS` e cria as tabelas e os índices da aplicação. O servidor PostgreSQL precisa ter pgvector instalado e o usuário da migration deve ter permissão para criar a extensão, caso ainda não esteja habilitada. As migrations não são executadas automaticamente na inicialização da API.

## Índice

- [Recursos](#recursos)
- [Arquitetura](#arquitetura)
- [Tecnologias](#tecnologias)
- [Requisitos](#requisitos)
- [Configuração local](#configuração-local)
- [Banco de dados e migrations](#banco-de-dados-e-migrations)
- [Execução](#execução)
- [Autenticação](#autenticação)
- [API](#api)
- [Busca semântica](#busca-semântica)
- [Modelo de dados](#modelo-de-dados)
- [Limites e validações](#limites-e-validações)
- [Observabilidade e prontidão](#observabilidade-e-prontidão)
- [Estrutura do repositório](#estrutura-do-repositório)
- [Testes e qualidade](#testes-e-qualidade)
- [Segurança operacional](#segurança-operacional)

## Recursos

- **Isolamento por tenant:** cada aplicação possui suas próprias chaves e coleções.
- **Chaves de API protegidas:** a chave completa é retornada somente na criação; o banco armazena seu hash SHA-256.
- **Coleções e metadados:** coleções vinculadas a um modelo, com configuração e metadados JSONB.
- **Inserção de vetores:** inserção individual e em lote, com deduplicação baseada no hash do texto de referência.
- **Busca por similaridade:** pesquisa por texto ou por um vetor fornecido pelo cliente, em uma ou mais coleções, com filtros avançados de metadados e utilização da métrica configurada para cada modelo (`cosine`, `l2` ou `ip`).
- **Várias dimensões:** armazenamento especializado para vetores de 256, 512, 768, 1024, 1536 e 3072 dimensões.
- **Geração local de embeddings:** modelos `SentenceTransformer` são carregados sob demanda, mantidos em cache no processo e usados para gerar vetores diretamente ou durante consultas, fora do event loop.
- **Telemetria de operações selecionadas:** eventos de inserção e busca são registrados em segundo plano.
- **Documentação OpenAPI:** disponibilizada pelo FastAPI em `/docs` e `/redoc`.

## Arquitetura

O fluxo geral de uma busca é:

1\. O cliente autentica-se com `X-API-Key`; a chave identifica a aplicação proprietária dos recursos.

2\. A API resolve as coleções solicitadas dentro do escopo dessa aplicação.

3\. As coleções são agrupadas pelo modelo de embedding associado.

4\. O serviço de inferência carrega (se necessário) o modelo configurado e transforma o texto da consulta em um vetor.

5\. A consulta usa a tabela correspondente à dimensão, aplica filtros JSONB e ordena os resultados pela métrica configurada no modelo (`cosine`, `l2` ou `ip`).

6\. Os resultados dos grupos podem ser mantidos na ordem de distância ou combinados por RRF e limitados por `top_k_global`.

As rotas HTTP ficam em `app/rotas/`; regras de negócio e acesso aos dados são separados em `app/services/`. Os modelos SQLAlchemy descrevem o schema esperado, enquanto Alembic é configurado para gerenciar suas alterações.

### Organização do frontend

O frontend do painel administrativo utiliza HTML, CSS e JavaScript nativo com ES Modules, sem dependência de frameworks JavaScript. O arquivo `admin.js` funciona como ponto de entrada e coordena os módulos especializados.

Os módulos JavaScript são organizados por responsabilidade:

- `core/`: estado compartilhado, comunicação com a API, autenticação, navegação, utilitários e formatação.
- `components/`: componentes reutilizáveis da interface, como diálogos, notificações, gráficos, ícones e cartões de estatísticas.
- `forms/`: construção dos formulários, processamento de submissões e tratamento dos dados enviados.
- `screens/`: carregamento e renderização das telas e funcionalidades do painel administrativo.

O arquivo `admin.html` define a estrutura da interface, `admin.css` concentra sua estilização e os módulos JavaScript implementam seu comportamento.

## Tecnologias

| Área | Tecnologia |
|---|---|
| API HTTP | FastAPI |
| Servidor ASGI | Uvicorn |
| Validação e configurações | Pydantic v2 e pydantic-settings |
| Persistência assíncrona | SQLAlchemy 2.x e asyncpg |
| Banco de dados | PostgreSQL |
| Busca vetorial | pgvector, com índices HNSW |
| Inferência local | sentence-transformers e NumPy |
| Migrations | Alembic |
| Estrutura do frontend | HTML5 |
| Estilização | CSS3 |
| Comportamento da interface | JavaScript nativo (ES Modules) |

As dependências Python estão listadas em [`requirements.txt`](./requirements.txt). As versões são especificadas majoritariamente como versões mínimas, não como um lockfile reproduzível.

## Requisitos

- Python compatível com as versões atuais das dependências listadas no `requirements.txt`.
- PostgreSQL com a extensão **pgvector** instalada e disponível no banco usado pela aplicação.
- Acesso de rede ao banco a partir do processo da API.
- Espaço em disco e memória suficientes para os modelos locais utilizados. O primeiro uso de um modelo pode exigir seu download do repositório configurado.

Instalar o pacote Python `pgvector` não instala a extensão dentro do servidor PostgreSQL. Em ambientes gerenciados, habilite a extensão conforme o procedimento do provedor.

## Configuração local

### 1. Criar e ativar um ambiente virtual

No PowerShell:

```powershell
py -m venv .venv
.\\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Em shells POSIX:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Definir as variáveis de ambiente

Crie um arquivo `.env` na raiz do projeto, usando [`.env.template`](./.env.template) como referência:

```dotenv
DATABASE_URL=postgresql+asyncpg://usuario:senha\@localhost:5432/cabore
ADMIN_KEY=substitua-por-um-segredo-aleatorio-com-pelo-menos-32-caracteres
DISPOSITIVO=cpu
AMBIENTE=desenvolvimento
```

| Variável | Obrigatória | Descrição |
|---|---:|---|
| `DATABASE_URL` | Sim | URL SQLAlchemy assíncrona. Deve usar o driver `postgresql+asyncpg`. |
| `ADMIN_KEY` | Sim | Segredo da administração, com no mínimo 32 caracteres. |
| `DISPOSITIVO` | Não | Dispositivo passado ao `SentenceTransformer`; o template usa `cpu`. |
| `AMBIENTE` | Não | `desenvolvimento` ou `producao`; o padrão é `producao`. Em desenvolvimento, o SQLAlchemy ativa `echo` para as instruções SQL. |

As configurações são validadas durante a inicialização. Valores incorretos ou variáveis obrigatórias ausentes impedem a aplicação de iniciar. Não versione o `.env` nem inclua valores reais de segredo em logs, exemplos ou tickets.

## Banco de dados e migrations

Os modelos em `app/models/modelos.py` descrevem tabelas para aplicações, chaves, modelos de embedding, coleções, embeddings e auditoria. A revisão `6fc3236d6e1c` cria a estrutura inicial, incluindo chaves estrangeiras, restrições, índices HNSW e GIN e as tabelas de embeddings para as dimensões inicialmente suportadas. A revisão `e81f48899ffb` acrescenta a tabela de embeddings de 256 dimensões. O tipo `vector` é usado para dimensões de até 1536; a dimensão 3072 usa `halfvec`.

O ambiente Alembic carrega a URL de `DATABASE_URL`. A migration executa `CREATE EXTENSION IF NOT EXISTS vector` antes de criar as tabelas, habilitando pgvector no banco se a extensão ainda não estiver habilitada. Para isso, os arquivos da extensão devem estar instalados no servidor PostgreSQL, e o usuário usado pela migration precisa ter as permissões necessárias. Em bancos gerenciados ou com permissões restritas, solicite ao provedor ou administrador que disponibilize/habilite pgvector.

Depois de instalar as dependências e configurar `.env`, aplique o schema na raiz do repositório:

```bash
alembic upgrade head
```

O comando aplica todas as revisões pendentes até `head`, habilita a extensão quando necessário e cria as tabelas e os índices definidos pelas migrations. Ele **altera o banco de dados**: execute-o somente no banco correto e após revisar as políticas de implantação do ambiente. A API não executa migrations durante a inicialização; isso evita que vários workers tentem alterar o schema simultaneamente e mantém a implantação do banco como uma etapa controlada.

Os downgrades removem as tabelas e os dados criados pelas revisões revertidas, mas mantêm a extensão pgvector instalada, pois ela pode ser compartilhada com outros objetos ou aplicações.

Em bancos já existentes, revise o schema e o histórico de Alembic antes de aplicar a revisão inicial, pois ela espera criar objetos que ainda não existam. Não marque a revisão como aplicada sem confirmar que as estruturas correspondentes existem. Não use `Base.metadata.create_all()` como substituto do versionamento do schema em produção.

## Execução

Com dependências e variáveis configuradas e após aplicar as migrations:

```bash
uvicorn app.main:app --reload
```

Por padrão, o Uvicorn atende em `http\://127.0.0.1:8000`. A opção `--reload` destina-se ao desenvolvimento; use um processo de execução apropriado ao ambiente em produção.

Interfaces da documentação:
- Swagger UI: `http\://127.0.0.1:8000/docs`
- ReDoc: `http\://127.0.0.1:8000/redoc`
- OpenAPI: `http\://127.0.0.1:8000/openapi.json`

## Autenticação

Há dois mecanismos distintos:

| Credencial | Header | Usada por |
|---|---|---|
| Chave administrativa | `X-Admin-Key` | Gerenciamento de aplicações, chaves, modelos e coleções; acesso ao painel e às funcionalidades administrativas. |
| Chave de aplicação (tenant) | `X-API-Key` | Operações de coleções, inserção/remoção de embeddings e busca. |

Exemplo:

```bash
curl http\://127.0.0.1:8000/v1/colecoes/ \\
  -H "X-API-Key: cb_sua_chave_de_aplicacao"
```

As chaves administrativas são comparadas em tempo constante. Chaves de aplicação são geradas aleatoriamente, armazenadas como hash SHA-256 e não podem ser recuperadas pela API depois da criação. Guarde a chave retornada no momento da emissão; se houver perda ou suspeita de exposição, revogue-a e crie outra.

O campo `publica` de uma coleção é metadado de visibilidade no modelo. As rotas de coleção e busca continuam exigindo uma chave de aplicação; não há, no código atual, um endpoint público anônimo.

## API

As rotas de negócio da API são prefixadas por `/v1`. Os endpoints de administração exigem `X-Admin-Key`; endpoints tenant exigem `X-API-Key`. As rotas de leitura de modelos indicadas como públicas não exigem nenhum desses headers. Os endpoints de saúde e prontidão (`/status` e `/ready`) e os recursos estáticos (`/static`) são disponibilizados fora desse prefixo.

### Painel administrativo

Acesse `/v1/admin/` para abrir o painel administrativo. A interface utiliza a `ADMIN_KEY` existente, armazenada somente na sessão do navegador; não cria uma conta ou senha de administrador. O painel oferece as seguintes funcionalidades:

- **Visão geral:** acompanhamento de indicadores, volume de requisições, latências, operações e atividade recente.
- **Aplicações:** cadastro, consulta, edição, suspensão, reativação e exclusão de aplicações.
- **Detalhes de aplicações:** visualização individual de indicadores e informações de utilização.
- **Coleções:** gerenciamento de coleções vinculadas às aplicações.
- **Chaves de API:** emissão, consulta e revogação de chaves.
- **Modelos:** cadastro, consulta e atualização dos modelos de embedding.
- **Infraestrutura:** acompanhamento da disponibilidade dos serviços e dos recursos utilizados pela aplicação.

A interface é implementada em HTML, CSS e JavaScript modular, com os arquivos organizados em `app/templates/` e `app/static/`. Em produção, publique o painel exclusivamente atrás de HTTPS.

O dashboard consulta `GET /v1/admin/analytics?dias=30` com `X-Admin-Key`. O parâmetro `dias` aceita valores entre 7 e 90. A resposta reúne totais, latência média e P95, resultados retornados, atividade diária, operações, aplicações mais ativas e as 15 requisições mais recentes. A auditoria registra apenas as operações que a API instrumenta atualmente; ela não representa falhas que não tenham sido registradas.

### Aplicações e chaves — administração

| Método | Caminho | Descrição |
|---|---|---|
| `GET` | `/v1/admin/` | Entrega a interface do painel administrativo. |
| `GET` | `/v1/admin/analytics?dias=30` | Retorna os indicadores e eventos da auditoria; exige `X-Admin-Key`. |
| `GET` | `/v1/aplicacoes/?limite=50&deslocamento=0` | Lista aplicações com paginação simples; exige `X-Admin-Key`. |
| `POST` | `/v1/aplicacoes/` | Cria uma aplicação (tenant). |
| `POST` | `/v1/aplicacoes/chaves` | Emite uma chave de API; a chave plana é retornada apenas nesta resposta. |
| `GET` | `/v1/aplicacoes/{aplicacao_id}/chaves` | Lista as chaves da aplicação, sem revelar os valores secretos. |
| `PATCH` | `/v1/aplicacoes/chaves/{chave_id}/revogar` | Revoga uma chave. |
| `PATCH` | `/v1/aplicacoes/{aplicacao_id}` | Atualiza o nome da aplicação. |
| `DELETE` | `/v1/aplicacoes/{aplicacao_id}` | Remove a aplicação e recursos dependentes via cascade. |
| `GET` | `/v1/aplicacoes/{aplicacao_id}/detalhes?dias=30` | Retorna informações detalhadas e indicadores de uma aplicação. |
| `PATCH` | `/v1/aplicacoes/{aplicacao_id}/status` | Suspende ou reativa uma aplicação. |

Criação de aplicação:

```bash
curl -X POST http\://127.0.0.1:8000/v1/aplicacoes/ \\
  -H "X-Admin-Key: $ADMIN_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"nome":"Minha aplicação"}'
```

Emissão de chave:

```bash
curl -X POST http\://127.0.0.1:8000/v1/aplicacoes/chaves \\
  -H "X-Admin-Key: $ADMIN_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"aplicacao_id":"UUID_DA_APLICACAO","nome":"Produção"}'
```

A resposta de criação da chave inclui `chave_api` e uma mensagem para armazená-la com segurança. Uma aplicação precisa existir antes de receber uma chave.

### Coleções — administração

| Método | Caminho | Descrição |
|---|---|---|
| `GET` | `/v1/admin/colecoes` | Lista coleções das aplicações, com filtros administrativos. |
| `POST` | `/v1/admin/colecoes` | Cria uma coleção para uma aplicação selecionada. |
| `PATCH` | `/v1/admin/colecoes/{colecao_id}` | Atualiza uma coleção no contexto administrativo. |
| `DELETE` | `/v1/admin/colecoes/{colecao_id}` | Remove uma coleção e seus embeddings. |

Todas essas rotas exigem `X-Admin-Key`.

### Modelos de embedding

| Método | Caminho | Acesso | Descrição |
|---|---|---|---|
| `GET` | `/v1/modelos/` | Público | Lista modelos cadastrados (`limite` padrão 50, máximo 100; `deslocamento` padrão 0). |
| `GET` | `/v1/modelos/{modelo_id}` | Público | Consulta um modelo pelo identificador. |
| `POST` | `/v1/modelos/` | Admin | Cadastra um modelo; dimensões aceitas: 256, 512, 768, 1024, 1536 ou 3072; métrica aceita: `cosine`, `l2` ou `ip`. |
| `PATCH` | `/v1/modelos/{modelo_id}` | Admin | Atualiza nome, provedor, repositório, métrica e estado ativo. |

O identificador `modelo_id` também é usado na configuração de coleções. Para a inferência local, informe `identificador_repositorio` quando o nome do repositório não coincidir com o identificador usado pela aplicação.

### Coleções — tenant

| Método | Caminho | Descrição |
|---|---|---|
| `POST` | `/v1/colecoes/` | Cria coleção vinculada automaticamente à aplicação autenticada. |
| `GET` | `/v1/colecoes/` | Lista coleções do tenant; aceita `limite` (1–1000, padrão 50) e `deslocamento` (0–10000). |
| `PATCH` | `/v1/colecoes/{colecao_id}` | Atualiza nome, configuração, metadados ou visibilidade. |
| `DELETE` | `/v1/colecoes/{colecao_id}` | Remove a coleção e seus embeddings associados. |

Exemplo de criação:

```bash
curl -X POST http\://127.0.0.1:8000/v1/colecoes/ \\
  -H "X-API-Key: cb_sua_chave_de_aplicacao" \\
  -H "Content-Type: application/json" \\
  -d '{
    "modelo_embedding_id": "sentence-transformers/all-MiniLM-L6-v2",
    "nome": "documentos",
    "tipo_armazenamento": "vector",
    "configuracao_embedding": {},
    "metadados": {"origem": "base-interna"},
    "publica": false
  }'
```

Use um modelo já cadastrado, com dimensão compatível com o modelo realmente usado para gerar os vetores. O exemplo de identificador acima é ilustrativo: o registro correspondente deve existir no banco e sua dimensão precisa ser suportada.

### Embeddings e busca — tenant

| Método | Caminho | Descrição |
|---|---|---|
| `POST` | `/v1/embeddings/` | Insere um embedding; exige `colecao_id`, `texto_referencia` e `vetor`. |
| `POST` | `/v1/embeddings/lote?colecao_id={uuid}` | Insere entre 1 e 100 embeddings para a coleção indicada. O corpo é uma lista JSON. |
| `POST` | `/v1/embeddings/gerar` | Gera o vetor de um texto usando o modelo e o repositório informados. |
| `POST` | `/v1/embeddings/buscar` | Busca por texto em uma ou mais coleções. |
| `POST` | `/v1/embeddings/buscar-vetor` | Busca por similaridade usando um vetor fornecido pelo cliente em uma coleção. |
| `DELETE` | `/v1/embeddings/{embedding_id}` | Remove um embedding; o corpo JSON deve informar `colecao_id`. |

O endpoint de geração exige uma chave de aplicação (`X-API-Key`). Envie `texto` (de 1 a 8192 caracteres), `id_modelo` (até 50 caracteres) e `repositorio` (até 550 caracteres) no corpo JSON. O repositório pode ser um identificador aceito pelo `SentenceTransformer` ou um caminho local acessível pelo processo da API. O modelo é carregado sob demanda e mantido em cache no processo.

Exemplo de geração:

```bash
curl -X POST http\://127.0.0.1:8000/v1/embeddings/gerar \\
  -H "X-API-Key: cb_sua_chave_de_aplicacao" \\
  -H "Content-Type: application/json" \\
  -d '{
    "texto": "Texto para transformar em representação vetorial.",
    "id_modelo": "meu-modelo",
    "repositorio": "sentence-transformers/all-MiniLM-L6-v2"
  }'
```

A resposta contém `vetor` (uma lista de números), `id_modelo` e `repositorio`. O tamanho do vetor depende do modelo utilizado; use um modelo com dimensão compatível com a coleção onde pretende armazená-lo.

Exemplo de inserção de um vetor:

```bash
curl -X POST http\://127.0.0.1:8000/v1/embeddings/ \\
  -H "X-API-Key: cb_sua_chave_de_aplicacao" \\
  -H "Content-Type: application/json" \\
  -d '{
    "colecao_id": "UUID_DA_COLECAO",
    "texto_referencia": "Conteúdo associado a este vetor",
    "vetor": [0.12, -0.08, 0.31],
    "metadados": {"categoria": "exemplo"}
  }'
```

O vetor acima é apenas ilustrativo e **não** corresponde a uma dimensão válida para um modelo cadastrado. Na aplicação real, envie uma lista numérica com exatamente o número de dimensões exigido pelo modelo da coleção. A rota de inserção recebe o vetor pronto; não gera o embedding do texto de referência.

Exemplo de consulta:

```bash

curl -X POST http\://127.0.0.1:8000/v1/embeddings/buscar \\
  -H "X-API-Key: cb_sua_chave_de_aplicacao" \\
  -H "Content-Type: application/json" \\
  -d '{
    "texto_consulta": "Como configurar o serviço?",
    "ids_colecoes": ["f4fad35c-ef24-44a8-8743-d611ecafcee6"],
    "top_k_colecao": 10,
    "top_k_global": 20,
    "estrategia_combinacao": "none",
    "filtro_metadados": {"categoria": "guia"}
  }'
```

No corpo de busca, `texto_consulta` é obrigatório. `ids_colecoes` e `ids_aplicacoes` são listas opcionais de UUIDs, com até 50 itens; não os envie simultaneamente. Quando `ids_colecoes` é informado, a busca aceita coleções próprias ou públicas. Com `ids_aplicacoes`, são consideradas coleções das aplicações informadas e públicas segundo o escopo descrito pela API. Sem nenhum identificador, a busca considera coleções próprias e coleções públicas.

`top_k_colecao` deve estar entre 1 e 100 e usa 10 por padrão. `top_k_global`, quando informado, deve ser maior que zero. `estrategia_combinacao` aceita `none` ou `rrf`; o modo RRF combina os rankings por conteúdo distinto e preserva as ocorrências selecionadas. A consulta semântica é gerada pelo serviço local de inferência; para cada modelo consultado, o processo precisa conseguir carregar seu modelo/repositório.

Para consultar diretamente com um vetor, envie `colecao_id`, `vetor` (lista de números) e, opcionalmente, `top_k` e `filtro_metadados`. `top_k` aceita valores entre 1 e 100 e usa 10 por padrão. O vetor deve ter exatamente a dimensão do modelo associado à coleção. Essa rota não gera embeddings: o cliente deve fornecer um vetor produzido de forma compatível com esse modelo.

Exemplo de busca por vetor:

```bash
curl -X POST http\://127.0.0.1:8000/v1/embeddings/buscar-vetor \\
  -H "X-API-Key: cb_sua_chave_de_aplicacao" \\
  -H "Content-Type: application/json" \\
  -d '{
    "colecao_id": "UUID_DA_COLECAO",
    "vetor": [0.12, -0.08, 0.31],
    "top_k": 10,
    "filtro_metadados": {
      "categoria": {"$in": ["guia", "manual"]},
      "prioridade": {"$gte": 2}
    }
  }'
```

O vetor do exemplo é ilustrativo; substitua-o por uma lista numérica com a dimensão exigida pelo modelo da coleção.

A resposta de busca inclui, para cada resultado, `id`, `colecao_id`, `conteudo_hash`, `distancia`, `metrica_distancia`, `score_relevancia`, `nome_modelo`, `modelo_dimensoes`, `metadados` e `criado_em`. Em `rrf`, `score_relevancia` contém o score calculado; fora desse modo, seu valor é `null`. Os vetores retornados não são incluídos.

Erros de validação de entrada retornam HTTP `422`; os demais status dependem da operação e são descritos também no OpenAPI. Erros comuns incluem credenciais inválidas (`401`/`403`), recurso não encontrado (`404`), conflito de nomes de chave (`409`) e dados semanticamente inválidos (`400`).

## Busca semântica

- A busca pode receber texto ou um vetor de consulta. Na busca por texto, o vetor é produzido com `sentence-transformers` usando o modelo associado a cada coleção; na busca por vetor, o cliente envia o vetor e consulta uma coleção por requisição.
- Coleções de modelos diferentes podem participar da mesma busca global; a aplicação gera uma consulta por modelo, consulta cada grupo e combina os resultados.
- Cada modelo pode usar a métrica `cosine`, `l2` ou `ip`. A interpretação da distância deve considerar a métrica registrada; o resultado não presume cosseno em todos os modelos.
- A combinação global pode ser desativada (`none`) ou usar Reciprocal Rank Fusion (`rrf`).
- Os filtros de metadados aceitam igualdade direta ou os operadores `$eq`, `$ne`, `$in`, `$nin`, `$gt`, `$gte`, `$lt` e `$lte`; também podem apontar para campos aninhados. Filtros em campos ou condições diferentes são combinados com AND. Os operadores relacionais aceitam apenas números finitos.
- O sistema limita os resultados por grupo e depois ordena e aplica o limite global informado.
- A inserção não invoca o serviço de inferência: a aplicação cliente deve calcular e enviar os vetores compatíveis com o modelo da coleção.

## Modelo de dados

| Entidade | Papel |
|---|---|
| `Aplicacao` | Tenant, com nome, estado ativo e relações com chaves e coleções. |
| `ChaveAPI` | Chave identificada por nome, associada ao tenant; o valor secreto não é persistido em claro. |
| `ModeloEmbedding` | Identificador, provedor, dimensão, repositório opcional, métrica e estado ativo do modelo. |
| `Colecao` | Agrupamento de embeddings associado a um tenant e a um modelo, incluindo JSONB e visibilidade. |
| `Embedding*` | Registro de vetor, hash de conteúdo, metadados e data de criação, armazenado em tabela dimensionada. |
| `AuditoriaRequisicao` | Operação, duração, quantidade de resultados e referências opcionais a tenant/coleção/chave. |

O hash de deduplicação é calculado a partir do texto de referência após `strip()` e conversão para minúsculas. A unicidade é por coleção e hash: conteúdo igual pode existir em coleções distintas.

## Limites e validações

- Texto de referência e texto de consulta: até **8192 caracteres**; não podem ser vazios ou conter apenas espaços.

- Vetor: entre 1 e **3072** valores finitos; a dimensão exata também precisa corresponder ao modelo.

- Lote de inserção: entre 1 e **100** itens.

- Busca: até **50** identificadores por lista; `top_k_colecao` entre 1 e **100**; `top_k_global`, quando informado, deve ser maior que zero.

- Dimensões cadastráveis: **256**, **512**, **768**, **1024**, **1536** e **3072**.

- Nomes de aplicação, coleção e chave: até **100 caracteres**.

- Os campos de metadados/configuração são objetos JSON.

## Observabilidade e prontidão

| Endpoint | Comportamento |
|---|---|
| `GET /status` | Confirma que o processo está ativo; não verifica dependências externas. |
| `GET /ready` | Executa `SELECT 1` no banco; retorna `503` se o banco falhar ou a verificação exceder 2 segundos. |
| `GET /v1/admin/health` | Consulta o estado da infraestrutura para o painel administrativo; exige `X-Admin-Key`. |

As rotas de inserção individual, inserção em lote e busca agendam auditoria em segundo plano. A telemetria não é parte da resposta síncrona; falhas SQL ao persistir esse registro são escritas no log. A auditoria não deve ser interpretada como trilha completa de todas as requisições da API.

## Estrutura do repositório

```text
.
├── app/
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── limites.py
│   ├── models/
│   │   ├── modelos.py
│   │   └── tipos.py
│   ├── rotas/
│   │   ├── admin_ui.py
│   │   ├── aplicacoes.py
│   │   ├── colecoes.py
│   │   ├── dependencias.py
│   │   ├── embeddings.py
│   │   ├── modelos.py
│   │   └── v1.py
│   ├── schemas/
│   │   └── schemas.py
│   ├── services/
│   │   ├── aplicacao_service.py
│   │   ├── auditoria_service.py
│   │   ├── busca_service.py
│   │   ├── colecao_service.py
│   │   ├── embedding_service.py
│   │   ├── inferencia_service.py
│   │   └── modelo_service.py
│   ├── templates/
│   │   └── admin.html
│   └── static/
│       ├── css/
│       │   └── admin.css
│       └── js/
│           ├── admin.js
│           ├── core/
│           │   ├── api.js
│           │   ├── authentication.js
│           │   ├── formatters.js
│           │   ├── navigation.js
│           │   ├── state.js
│           │   └── utils.js
│           ├── components/
│           │   ├── charts.js
│           │   ├── dialogs.js
│           │   ├── icons.js
│           │   ├── notifications.js
│           │   └── stat-card.js
│           ├── forms/
│           │   ├── application-form.js
│           │   ├── collection-form.js
│           │   ├── form-handler.js
│           │   ├── key-form.js
│           │   ├── model-form.js
│           │   └── submission-handlers.js
│           └── screens/
│               ├── actions.js
│               ├── application-details.js
│               ├── applications.js
│               ├── collections.js
│               ├── dashboard.js
│               ├── infrastructure.js
│               ├── keys.js
│               └── models.js
├── alembic/
│   ├── env.py
│   └── versions/
├── alembic.ini
├── requirements.txt
└── .env.template
```

### Organização do frontend

O arquivo `admin.js` é o ponto de entrada da interface administrativa. Ele importa e coordena os módulos responsáveis pelas funcionalidades do painel.

| Diretório | Responsabilidade |
|---|---|
| `core/` | Estado compartilhado, comunicação com a API, autenticação, navegação, utilitários e formatação. |
| `components/` | Componentes reutilizáveis da interface, como diálogos, notificações, gráficos, ícones e cartões de estatísticas. |
| `forms/` | Construção dos formulários, processamento de submissões e tratamento dos dados enviados. |
| `screens/` | Carregamento e renderização das telas e funcionalidades específicas do painel. |

O arquivo `admin.html` define a estrutura da interface, `admin.css` concentra sua estilização e os módulos JavaScript implementam seu comportamento.

## Testes e qualidade

Não há diretório de testes nem configuração de runner de testes no repositório atual. Antes de releases, adicione cobertura para autenticação e isolamento entre tenants, validação de dimensões, deduplicação, filtros JSONB, migrations e busca com modelos de dimensões diferentes.

Verificações manuais iniciais após preparar o banco e aplicar as migrations:

1\. A API inicia com variáveis válidas e falha claramente com configurações inválidas.

2\. `/status` responde sem banco e `/ready` reflete a disponibilidade do banco.

3\. Uma chave de tenant não acessa coleções ou embeddings de outro tenant.

4\. Vetores de dimensão incompatível e entradas fora dos limites são rejeitados.

5\. A busca carrega o modelo esperado, aplica filtro de metadados e ordena por distância.

## Segurança operacional

- Use HTTPS em qualquer ambiente acessível por rede não confiável.
- Gere `ADMIN_KEY` com um gerador criptograficamente seguro; use segredos distintos por ambiente e não o reutilize como chave de tenant.
- Armazene as chaves emitidas em um gerenciador de segredos e nunca as registre em logs.
- Restrinja permissões do usuário PostgreSQL e o acesso de rede ao banco.
- Confirme a disponibilidade de pgvector e as permissões necessárias para aplicar migrations.
- Planeje downloads, cache, memória e atualização dos modelos Hugging Face usados para inferência.
- Aplique e valide as migrations antes de expor a aplicação a tráfego ou armazenar dados.
