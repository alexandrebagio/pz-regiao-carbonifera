# Teste do terreno de Criciúma na Build 42.22

O usuário confirmou que a primeira versão apareceu e carregou no jogo. A revisão **0.2**, já instalada, corrige as ruas e acrescenta a prévia vetorial. Falta conferir essas duas correções em um mundo novo.

## Correções da revisão 0.2

- **Asfalto:** a antiga regra Medium Asphalt usava a família `blends_street_01_96..111`, que nesta tilesheet tem aparência bege. O gerador agora usa RGB `100,100,100`, Dark Asphalt, família `80..95`. Os cinco TMX e as quatro células compiladas foram atualizados. A família nova foi confirmada nos cabeçalhos binários e as referências antigas não aparecem mais nos LOTs.
- **Prévia:** a tela de seleção de local da Build 42.22 usa os dados de `worldmap`, e não `thumb.png`. Foram acrescentados `worldmap.xml` e `worldmap.xml.bin` com ruas, caminhos e água. O WorldEd normalizou as geometrias, sem rejeitar feições, e o leitor da instalação do jogo carregou quatro células e 67 feições. O log está em `mapping/validacao_worldmap_jogo.log`.
- **Zonas:** foi acrescentado um `objects.lua` vazio, compatível com esta fase sem zonas manuais, para resolver o aviso de arquivo ausente registrado pelo jogo.

As feições da prévia seguem o terreno efetivamente exportado. Não incluem os contornos dos edifícios que ainda não foram construídos. Os arquivos anteriores à troca de asfalto estão em `mapping/backups/antes_asfalto_v02`.

## Como testar agora

1. Feche e reabra o Project Zomboid na Build 42.22 para carregar os arquivos atualizados.
2. Ative **Criciuma - Prototipo Centro**, ID `RegiaoCarboniferaPrototipo`.
3. Crie um **mundo novo de teste**, por exemplo `Criciuma_Prototipo_02`. O mundo anterior pode manter chunks já salvos com a textura antiga.
4. Escolha o local de nascimento **Criciuma - Centro (Prototipo)**. Um Sandbox com população de zumbis desativada facilita a inspeção.
5. O personagem deve nascer no asfalto perto da Praça Nereu Ramos: **X=25871, Y=25857, Z=0**. Todas as profissões do projeto usam esse ponto de teste.
6. Caminhe pelas ruas e atravesse o encontro das quatro células. Observe pisos ausentes, colisões inesperadas e erros de carregamento.
7. Confira a prévia na escolha do local e a aparência de asfalto escuro durante a partida.

Esta fase contém terreno, ruas, caminhos e água. Os edifícios marrons da prévia ainda são referências, sem construções jogáveis ou interiores. A densidade de zumbis exportada é zero; as opções de população do Sandbox também influenciam o ensaio.

## Arquivos prontos

| Entrega | Local |
| --- | --- |
| Projeto completo, quatro células Native256 | `mapping/centro_criciuma.pzw` |
| Quatro TMX de 256 × 256 | `mapping/tmx/centro/terreno_X_Y.tmx` |
| Projeto isolado | `mapping/teste_uma_celula.pzw` |
| TMX isolado | `mapping/tmx/teste/centro_0_0_0_0.tmx` |
| Mod exportado | `mod/RegiaoCarboniferaPrototipo` |
| Mod instalado | `C:\Users\alexa\Zomboid\mods\RegiaoCarboniferaPrototipo` |
| Resultado da validação | `mapping/validacao_conversao.json` |
| Spawn e instalação | `mapping/teste_jogo.json` |
| Conversão/exportação no editor | `mapping/conversao_worlded.log` |
| Checagem LOT pelo WorldEd | `mapping/validacao_lot_sources.log` |
| Projetos anteriores à conversão | `mapping/backups/antes_conversao` |

O mod usa a estrutura `common` + `42.0`, criada pelo exportador do WorldEd. Os arquivos compilados ficam em `common/media/maps/CriciumaCentroTeste`. Os `.source` editáveis permanecem no projeto e não foram copiados para a instalação do jogo.

## Verificações concluídas

- Cinco TMX com orientação `levelisometric`, 256 × 256 e 15 camadas.
- Bitmap incorporado em cada TMX idêntico ao PNG original, pixel a pixel.
- Dois PZW salvos com os respectivos TMX associados.
- Células compiladas `100,100`, `101,100`, `100,101` e `101,101`, cada uma com `.lotheader`, `.lotpack` e `chunkdata`.
- WorldEd reportou **4 células e 0 problemas de exportação**, com zero edifícios/quartos nesta fase.
- A checagem `--check-lot-sources` aprovou as quatro células, com código de saída 0.
- Cada LOT source descreve 1.024 chunks de 8 × 8 e 65.536 quadrados com piso, no nível zero.
- Spawn situado em uma área de 3 × 3 tiles de asfalto no raster original.
- Biomemaps RGB de 256 × 256 por célula: vermelho 0, sem bioma procedural explícito; verde 115 para TownZone, 64 para ForagingNav nas vias e 0 para Water.
- Os 31 arquivos instalados foram conferidos por SHA256 com o pacote do projeto.

O primeiro carregamento foi confirmado pelo usuário. A aparência do asfalto e a prévia da revisão 0.2 precisam de um novo ensaio visual; o validador de arquivos não substitui essa conferência.

## Posição e ferramentas

A origem global **100,100** é apenas uma posição de teste no jogo; o recorte geográfico continua centrado na Praça Nereu Ramos. Os LOTs originais instalados ocupam células X 0–77, Y 0–62. O protótipo está fora desses limites. O `map.info` usa `Muldraugh, KY` como base. Não existe uma estrada ligando o recorte a Kentucky.

- Editores: `C:\pz\PZTools\43.00B261119d\bin`.
- Tilesheets fornecidas pelo usuário: `C:\pz\tilesheets_42.22`, 540 PNGs.
- Jogo: `C:\Program Files (x86)\Steam\steamapps\common\ProjectZomboid`.
- Caminhos compartilhados: `C:\pz\PZTools\43.00B261119d\settings\PZTools.ini`.

O catálogo geral informa sete folhas ausentes: `alokin_test_sheet`, `bed_overlays_large`, `blends_natural_01_TEST`, `camping_03 (ayrton orio's conflicted copy 2025-09-10)`, `camping_04_on`, `floors_overlay_wood_01` e `location_orphanage`. As 18 folhas exigidas por Rules/Blends estavam disponíveis; os avisos não impediram a conversão/exportação. Nenhuma entrada foi removida para esconder os avisos.

## Repetir verificações

Para abrir o projeto completo:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\abrir_worlded.ps1
```

Após nova exportação, prepare e reinstale os arquivos complementares:

```powershell
.\.venv\Scripts\python.exe scripts\preparar_teste_jogo.py --instalar
.\.venv\Scripts\python.exe scripts\validar_conversao.py
```

O instalador não habilita o mod automaticamente e não altera saves. Ele preserva arquivos instalados que tenham sido modificados manualmente. Regenerar PNGs não atualiza TMX/LOT automaticamente. Preserve alterações manuais antes de reconverter células.

## Registro do ensaio

- [x] Editores, regras e tilesheets configurados.
- [x] Imagens convertidas para TMX.
- [x] Quatro células compiladas e verificadas.
- [x] Spawn, biomemaps e metadados preparados.
- [x] Mod de teste instalado localmente.
- [x] Mod apareceu e pôde ser habilitado no jogo, na versão inicial.
- [x] Local de nascimento apareceu na criação do mundo, na versão inicial.
- [ ] Personagem nasceu e caminhou nas ruas.
- [ ] Travessia entre células ocorreu sem pisos ausentes ou erros.
- [ ] Traçado conferido por alguém que conhece o centro.
- [ ] Prévia e asfalto escuro da revisão 0.2 conferidos em um mundo novo.

## Referências

- [Release dos editores utilizado](https://github.com/Unjammer/PZ_Mapping_Tools/releases/tag/43.00B261119d).
- [Documentação do mantenedor](https://github.com/Unjammer/PZ_Mapping_Tools/blob/main/DOCUMENTATION.md).
- [Referência de BiomeMapConfig](https://github.com/Unjammer/PZ_Mapping_Tools/blob/43.00B261119d/docs/PZ-B42.20-BiomeMapConfig.md).
- Metadados de mapa e spawnpoints foram conferidos nos arquivos locais do jogo. A origem geográfica é a [Praça Nereu Ramos no OSM](https://www.openstreetmap.org/way/165773276).
