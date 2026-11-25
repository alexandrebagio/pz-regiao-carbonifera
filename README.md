# Região Carbonífera no Project Zomboid

Protótipo do centro de Criciúma, com a Praça Nereu Ramos como referência. O projeto transforma OpenStreetMap em terreno, mapas TMX e células compiladas para testar a escala antes de expandir para Forquilhinha e Içara.

## Revisão 0.3

O mapa foi ampliado para **1.024 × 1.024 tiles**, em **16 células Native256**. A área geográfica continua sendo a mesma: **1.536 × 1.536 metros reais**, agora a **1,5 metro real por tile**.

| Via | Largura de asfalto |
| --- | --- |
| Ruas residenciais, acessos e ruas locais | mínimo de 8 tiles, espaço de duas faixas de 4 |
| Vias terciárias | 10 tiles |
| Vias secundárias | 12 tiles |
| Avenidas principais | 14 tiles |
| Caminhos de pedestres e escadas | 2 tiles, separados das vias de veículos |

A revisão também inclui um ajuste específico para a **prévia da tela de criação do mundo**. Ela carrega os vetores locais e usa um estilo próprio de prévia, sem inicializar os dados de exploração de uma partida.

O mod **Criciuma - Prototipo Centro** está instalado em `C:\Users\alexa\Zomboid\mods\RegiaoCarboniferaPrototipo`. A versão 0.3 requer **um mundo novo de teste**. Os saves antigos preservam chunks da escala anterior.

Ainda é um teste de terreno: **não há edifícios jogáveis, interiores, loot ou decoração**. Os contornos marrons da prévia geográfica são referências do OSM.

## Abrir e testar

- [Prévia geográfica](output/centro/previa.png).
- [Roteiro do teste](docs/primeiro_teste_worlded.md).
- [Validação das conversões](mapping/validacao_conversao.json).
- [Larguras por classe de via](mapping/larguras_v03.json).

No jogo, ative **Criciuma - Prototipo Centro**, crie um mundo novo e selecione **Criciuma - Centro (Prototipo)**. O ponto de nascimento da revisão 0.3 é **26140,26115,0**, no asfalto perto da praça. Um Sandbox sem população de zumbis facilita medir as ruas.

Para abrir o WorldEd na raiz do projeto:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\abrir_worlded.ps1
```

O projeto completo é `mapping/centro_criciuma.pzw`, agora de 4 × 4 células. O projeto `mapping/teste_uma_celula.pzw` contém um recorte isolado. Há 17 TMX no total.

## Ambiente

- Python 3.12 de 64 bits, em `.venv`.
- Editores em `C:\pz\PZTools\43.00B261119d`.
- Tilesheets fornecidas pelo usuário em `C:\pz\tilesheets_42.22`, 540 PNGs.
- Jogo em `C:\Program Files (x86)\Steam\steamapps\common\ProjectZomboid`.
- Parâmetros geográficos em `config/centro.json`; caminhos locais em `config/ferramentas.json`.
- CRS métrico WGS84 / UTM 22S, **EPSG:32722**. Origem raster no noroeste; X a leste e Y a sul.

O ambiente já está preparado. Em outra máquina com Python 3.12, execute `preparar.ps1`. As dependências geográficas estão em `requirements-lock.txt`; as ferramentas opcionais de automação de interface, em `requirements-ferramentas.txt`.

## Geração e validação

```powershell
.\.venv\Scripts\python.exe scripts\gerar_centro.py --offline
.\.venv\Scripts\python.exe scripts\validar_saida.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

O snapshot local evita novas consultas ao OSM. Para atualizá-lo, use `--atualizar-osm`. A consulta inicial retornou 1.037 feições no recorte, 410 segmentos de ruas/caminhos e 520 polígonos de edifícios. Na escala atual, 24 polígonos ocupam menos de 16 tiles quadrados. A cobertura de edifícios é incompleta, especialmente ao norte.

**Regenerar PNGs não atualiza os TMX e LOTs automaticamente.** Para substituir terrenos gerados sem edições manuais, `scripts/expandir_projeto.py` monta as células usando o template TMX já convertido pelo WorldEd e faz backup dos arquivos. Depois, exporte os LOTs no WorldEd com origem **100,100**, fontes editáveis habilitadas e o `zombiespawn.png` de 128 × 128.

Após nova exportação:

```powershell
.\.venv\Scripts\python.exe scripts\preparar_teste_jogo.py --instalar
.\.venv\Scripts\python.exe scripts\validar_conversao.py
```

O preparador adiciona spawn, biomemaps, metadados e a prévia da criação. O instalador preserva arquivos locais alterados manualmente, não habilita o mod automaticamente e não modifica saves. Os `.source` ficam no projeto.

Os validadores conferem a identidade dos pixels entre PNG/TMX, a grade de 256 tiles, os pisos compilados, a textura de asfalto, o spawn, os biomemaps, o worldmap e os hashes dos arquivos instalados. A travessia de dois veículos no jogo continua sendo uma validação prática a realizar.

## Estrutura

```text
config/                    escala, caminhos e template Lua da prévia
scripts/                   geração, instalação e validação
scripts/diagnosticos/       leitor de worldmap usando classes do jogo
 tests/                    casos espaciais sintéticos
data/raw/                  snapshot OSM e cache de consultas
data/processed/            feições recortadas em GeoJSON
output/centro/             PNGs, vetores e manifesto geográfico
mapping/                   PZW, TMX, relatórios e backups
mod/RegiaoCarboniferaPrototipo/  mod compilado e fontes editáveis
```

Os LOTs da revisão 0.3 ocupam as células globais **100–103 em X e Y**. Essa posição de teste não tem conexão rodoviária com Kentucky. A imagem `_veg` vazia e os biomemaps sem bioma procedural explícito servem apenas ao teste de terreno.

Próximas etapas: testar dois veículos em sentidos opostos, conferir as proporções com referências locais e então acrescentar calçadas, sinalização e edifícios jogáveis.

Dados geográficos: **© OpenStreetMap contributors**, [ODbL / atribuição](https://www.openstreetmap.org/copyright). Preserve `ATRIBUICAO.txt` ao compartilhar os dados e derivados.
