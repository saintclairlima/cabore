# Caboré

**API assíncrona de busca semântica e recomendação baseada em embeddings.**

Caboré é um serviço HTTP para organizar coleções vetoriais por aplicação (tenant), armazenar embeddings com metadados e consultar conteúdos semanticamente próximos a partir de texto. O projeto combina FastAPI, PostgreSQL, pgvector e modelos de embedding executados localmente por `sentence-transformers`.

> **Banco de dados:** a migration inicial `0da3b9845fd9` habilita a extensão `vector` com `CREATE EXTENSION IF NOT EXISTS` e cria as tabelas e os índices da aplicação. O servidor PostgreSQL precisa ter pgvector instalado e o usuário da migration deve ter permissão para criar a extensão, caso ainda não esteja habilitada. As migrations não são executadas automaticamente na inicialização da API.

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
- **Busca por similaridade de cosseno:** pesquisa por texto em uma ou mais coleções, com filtro opcional de metadados.
- **Várias dimensões:** armazenamento especializado para vetores de 512, 768, 1024, 1536 e 3072 dimensões.
- **Inferência local para consultas:** modelos `SentenceTransformer` são carregados sob demanda, mantidos em cache no processo e executados fora do event loop.
- **Telemetria de operações selecionadas:** eventos de inserção e busca são registrados em segundo plano.
- **Documentação OpenAPI:** disponibilizada pelo FastAPI em `/docs` e `/redoc`.

## Arquitetura

O fluxo geral de uma busca é:

1. O cliente autentica-se com `X-API-Key`; a chave identifica a aplicação proprietária dos recursos.
2. A API resolve as coleções solicitadas dentro do escopo dessa aplicação.
3. As coleções são agrupadas pelo modelo de embedding associado.
4. O serviço de inferência carrega (se necessário) o modelo configurado e transforma o texto da consulta em um vetor.
5. A consulta usa a tabela correspondente à dimensão, aplica filtros JSONB e ordena os resultados pela distância de cosseno.
6. Os resultados dos grupos são reunidos e limitados ao `limite` global pedido.

As rotas HTTP ficam em `app/rotas/`; regras de negócio e acesso aos dados são separados em `app/services/`. Os modelos SQLAlchemy descrevem o schema esperado, enquanto Alembic é configurado para gerenciar suas alterações.

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
.\.venv\Scripts\Activate.ps1
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
DATABASE_URL=postgresql+asyncpg://usuario:senha@localhost:5432/cabore
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

Os modelos em `app/models/modelos.py` descrevem tabelas para aplicações, chaves, modelos de embedding, coleções, embeddings e auditoria. A revisão `0da3b9845fd9` materializa esse schema, incluindo chaves estrangeiras, restrições, índices HNSW e GIN e as tabelas de embeddings para cada dimensão suportada. O tipo `vector` é usado para dimensões de até 1536; a dimensão 3072 usa `halfvec`.

O ambiente Alembic carrega a URL de `DATABASE_URL`. A migration executa `CREATE EXTENSION IF NOT EXISTS vector` antes de criar as tabelas, habilitando pgvector no banco se a extensão ainda não estiver habilitada. Para isso, os arquivos da extensão devem estar instalados no servidor PostgreSQL, e o usuário usado pela migration precisa ter as permissões necessárias. Em bancos gerenciados ou com permissões restritas, solicite ao provedor ou administrador que disponibilize/habilite pgvector.

Depois de instalar as dependências e configurar `.env`, aplique o schema na raiz do repositório:

```bash
alembic upgrade head
```

O comando aplica a migration, habilita a extensão quando necessário e cria as tabelas e os índices automaticamente. Ele **altera o banco de dados**: execute-o somente no banco correto e após revisar as políticas de implantação do ambiente. A API não executa migrations durante a inicialização; isso evita que vários workers tentem alterar o schema simultaneamente e mantém a implantação do banco como uma etapa controlada.

O downgrade remove as tabelas e os dados da aplicação criados por esta revisão, mas mantém a extensão pgvector instalada, pois ela pode ser compartilhada com outros objetos ou aplicações.

Em bancos já existentes, revise o schema e o histórico de Alembic antes de aplicar a revisão inicial, pois ela espera criar objetos que ainda não existam. Não marque a revisão como aplicada sem confirmar que as estruturas correspondentes existem. Não use `Base.metadata.create_all()` como substituto do versionamento do schema em produção.

## Execução

Com dependências e variáveis configuradas e após aplicar as migrations:

```bash
uvicorn app.main:app --reload
```

Por padrão, o Uvicorn atende em `http://127.0.0.1:8000`. A opção `--reload` destina-se ao desenvolvimento; use um processo de execução apropriado ao ambiente em produção.

Interfaces da documentação:

- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`
- OpenAPI: `http://127.0.0.1:8000/openapi.json`

## Autenticação

Há dois mecanismos distintos:

| Credencial | Header | Usada por |
|---|---|---|
| Chave administrativa | `X-Admin-Key` | Criação e gerenciamento de aplicações e chaves; criação e atualização de modelos. |
| Chave de aplicação (tenant) | `X-API-Key` | Operações de coleções, inserção/remoção de embeddings e busca. |

Exemplo:

```bash
curl http://127.0.0.1:8000/v1/colecoes/ \
  -H "X-API-Key: cb_sua_chave_de_aplicacao"
```

As chaves administrativas são comparadas em tempo constante. Chaves de aplicação são geradas aleatoriamente, armazenadas como hash SHA-256 e não podem ser recuperadas pela API depois da criação. Guarde a chave retornada no momento da emissão; se houver perda ou suspeita de exposição, revogue-a e crie outra.

O campo `publica` de uma coleção é metadado de visibilidade no modelo. As rotas de coleção e busca continuam exigindo uma chave de aplicação; não há, no código atual, um endpoint público anônimo.

## API

Todas as rotas funcionais abaixo são prefixadas por `/v1`. Os endpoints de administração exigem `X-Admin-Key`; endpoints tenant exigem `X-API-Key`. As rotas de leitura de modelos indicadas como públicas não exigem nenhum desses headers.

### Aplicações e chaves — administração

| Método | Caminho | Descrição |
|---|---|---|
| `POST` | `/v1/aplicacoes/` | Cria uma aplicação (tenant). |
| `POST` | `/v1/aplicacoes/chaves` | Emite uma chave de API; a chave plana é retornada apenas nesta resposta. |
| `GET` | `/v1/aplicacoes/{aplicacao_id}/chaves` | Lista as chaves da aplicação, sem revelar os valores secretos. |
| `PATCH` | `/v1/aplicacoes/chaves/{chave_id}/revogar` | Revoga uma chave. |
| `PATCH` | `/v1/aplicacoes/{aplicacao_id}` | Atualiza o nome da aplicação. |
| `DELETE` | `/v1/aplicacoes/{aplicacao_id}` | Remove a aplicação e recursos dependentes via cascade. |

Criação de aplicação:

```bash
curl -X POST http://127.0.0.1:8000/v1/aplicacoes/ \
  -H "X-Admin-Key: $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"nome":"Minha aplicação"}'
```

Emissão de chave:

```bash
curl -X POST http://127.0.0.1:8000/v1/aplicacoes/chaves \
  -H "X-Admin-Key: $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"aplicacao_id":"UUID_DA_APLICACAO","nome":"Produção"}'
```

A resposta de criação da chave inclui `chave_api` e uma mensagem para armazená-la com segurança. Uma aplicação precisa existir antes de receber uma chave.

### Modelos de embedding

| Método | Caminho | Acesso | Descrição |
|---|---|---|---|
| `GET` | `/v1/modelos/` | Público | Lista modelos cadastrados (`limite` padrão 50, máximo 100; `deslocamento` padrão 0). |
| `GET` | `/v1/modelos/{modelo_id}` | Público | Consulta um modelo pelo identificador. |
| `POST` | `/v1/modelos/` | Admin | Cadastra um modelo; dimensões aceitas: 512, 768, 1024, 1536 ou 3072. |
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
curl -X POST http://127.0.0.1:8000/v1/colecoes/ \
  -H "X-API-Key: cb_sua_chave_de_aplicacao" \
  -H "Content-Type: application/json" \
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
| `POST` | `/v1/embeddings/lote?colecao_id={uuid}` | Insere uma lista de embeddings para a coleção indicada. |
| `POST` | `/v1/embeddings/buscar` | Busca por texto em uma ou mais coleções. |
| `DELETE` | `/v1/embeddings/{embedding_id}` | Remove um embedding; o corpo JSON deve informar `colecao_id`. |

Exemplo de inserção de um vetor:

```bash
curl -X POST http://127.0.0.1:8000/v1/embeddings/ \
  -H "X-API-Key: cb_sua_chave_de_aplicacao" \
  -H "Content-Type: application/json" \
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
curl -X POST http://127.0.0.1:8000/v1/embeddings/buscar \
  -H "X-API-Key: cb_sua_chave_de_aplicacao" \
  -H "Content-Type: application/json" \
  -d '{
    "colecoes_nomes_ou_ids": ["documentos"],
    "texto_consulta": "Como configurar o serviço?",
    "limite": 10,
    "filtro_metadados": {"categoria": "guia"}
  }'
```

No corpo de busca, `colecoes_nomes_ou_ids` aceita entre 1 e 50 identificadores, `texto_consulta` é obrigatório e `limite` aceita valores entre 1 e 100 (padrão 10). Use identificadores do mesmo tipo em uma consulta: a implementação decide se interpreta a lista como UUIDs ou nomes a partir do primeiro item. A consulta semântica é gerada pelo serviço local de inferência; para cada modelo consultado, o processo precisa conseguir carregar seu modelo/repositório.

A resposta de busca inclui, para cada resultado, `id`, `colecao_id`, `conteudo_hash`, `distancia`, `metadados` e `criado_em`. A distância menor representa maior proximidade segundo a métrica de cosseno. Os vetores retornados não são incluídos.

Erros de validação de entrada retornam HTTP `422`; os demais status dependem da operação e são descritos também no OpenAPI. Erros comuns incluem credenciais inválidas (`401`/`403`), recurso não encontrado (`404`), conflito de nomes de chave (`409`) e dados semanticamente inválidos (`400`).

## Busca semântica

- A busca aceita texto, não um vetor de consulta enviado pelo cliente.
- O vetor da consulta é produzido com `sentence-transformers` usando o modelo associado a cada coleção solicitada.
- Coleções de modelos diferentes podem participar da mesma busca global; a aplicação consulta cada grupo por modelo e junta os resultados.
- Apenas a métrica `cosine` é aceita pelo fluxo atual.
- Metadados são filtrados por contenção JSONB; informe um objeto JSON que deve estar contido nos metadados do resultado.
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
- Busca: entre 1 e **50** coleções; até **100** resultados.
- Dimensões cadastráveis: **512**, **768**, **1024**, **1536** e **3072**.
- Nomes de aplicação, coleção e chave: até **100 caracteres**.
- Os campos de metadados/configuração são objetos JSON.

## Observabilidade e prontidão

| Endpoint | Comportamento |
|---|---|
| `GET /status` | Confirma que o processo está ativo; não verifica dependências externas. |
| `GET /ready` | Executa `SELECT 1` no banco; retorna `503` se o banco falhar ou a verificação exceder 2 segundos. |

As rotas de inserção individual, inserção em lote e busca agendam auditoria em segundo plano. A telemetria não é parte da resposta síncrona; falhas SQL ao persistir esse registro são escritas no log. A auditoria não deve ser interpretada como trilha completa de todas as requisições da API.

## Estrutura do repositório

```text
.
├── app/
│   ├── main.py                 # Inicialização FastAPI, handlers e health checks
│   ├── config.py               # Configurações e validação de ambiente
│   ├── database.py             # Engine, sessão async e Base declarativa
│   ├── limites.py              # Limites compartilhados de entrada
│   ├── models/                 # Entidades SQLAlchemy e tipos
│   ├── rotas/                  # Endpoints HTTP agrupados por domínio
│   ├── schemas/                # Schemas Pydantic de entrada e saída
│   └── services/               # Regras de negócio, persistência e inferência
├── alembic/
│   ├── env.py                  # Integração Alembic/SQLAlchemy assíncrona
│   └── versions/               # Revisões de schema
├── alembic.ini                 # Configuração Alembic
├── requirements.txt            # Dependências Python
└── .env.template               # Exemplo de variáveis de ambiente
```

## Testes e qualidade

Não há diretório de testes nem configuração de runner de testes no repositório atual. Antes de releases, adicione cobertura para autenticação e isolamento entre tenants, validação de dimensões, deduplicação, filtros JSONB, migrations e busca com modelos de dimensões diferentes.

Verificações manuais iniciais após preparar o banco e aplicar as migrations:

1. A API inicia com variáveis válidas e falha claramente com configurações inválidas.
2. `/status` responde sem banco e `/ready` reflete a disponibilidade do banco.
3. Uma chave de tenant não acessa coleções ou embeddings de outro tenant.
4. Vetores de dimensão incompatível e entradas fora dos limites são rejeitados.
5. A busca carrega o modelo esperado, aplica filtro de metadados e ordena por distância.

## Segurança operacional

- Use HTTPS em qualquer ambiente acessível por rede não confiável.
- Gere `ADMIN_KEY` com um gerador criptograficamente seguro; use segredos distintos por ambiente e não o reutilize como chave de tenant.
- Armazene as chaves emitidas em um gerenciador de segredos e nunca as registre em logs.
- Restrinja permissões do usuário PostgreSQL e o acesso de rede ao banco.
- Confirme a disponibilidade de pgvector e as permissões necessárias para aplicar migrations.
- Planeje downloads, cache, memória e atualização dos modelos Hugging Face usados para inferência.
- Aplique e valide as migrations antes de expor a aplicação a tráfego ou armazenar dados.
