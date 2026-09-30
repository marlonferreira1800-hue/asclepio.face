# Face Inteligente

MVP desktop para Windows que processa a webcam **inteiramente no computador** e apresenta uma **ativação fisiológica estimada**. É um protótipo pessoal e experimental: não diagnostica ansiedade, não rotula pessoas, não detecta mentiras, não reconhece identidade e não afirma emoções com certeza.

## Privacidade e consentimento

- A câmera só começa depois de um aviso e de consentimento explícito.
- Imagens não são enviadas, identificadas ou gravadas.
- O salvamento é desativado por padrão.
- Quando habilitado, somente métricas numéricas são salvas em `data/sessions.db`.
- Sessões salvas podem ser exportadas em CSV ou excluídas pela interface.

Calor, exercício, cafeína, movimento, iluminação, doenças, medicamentos, características da pele, maquiagem, óculos e limitações da câmera podem alterar os sinais. O resultado não substitui avaliação profissional ou equipamento clínico.

## Recursos do MVP

- seleção, início e parada de webcam;
- vídeo ao vivo sem gravação, com indicação de enquadramento;
- MediaPipe Face Mesh quando disponível, com fallback para detecção facial Haar do OpenCV;
- piscadas com EAR quando há pontos faciais e movimento de cabeça por deslocamento normalizado;
- brilho, nitidez/desfoque, FPS, rosto presente, estabilidade e qualidade agregada;
- gráfico em tempo real de qualidade e ativação;
- calibração individual configurável (10–120 s; recomendado 60–90 s);
- modelo baseado em regras, transparente e bloqueado quando a qualidade é insuficiente;
- rPPG experimental com janela temporal, confiança espectral e ocultação automática em sinal ruim;
- resumo, SQLite opcional, CSV e exclusão de sessões;
- encerramento limpo e mensagens para câmera/dependência ausente.

## Versão Web & Deploy no Netlify

O projeto conta com uma versão Web completa em HTML5, CSS e JavaScript (client-side) compatível com **Netlify**, **Vercel** e **GitHub Pages**:

1. Acesse [app.netlify.com](https://app.netlify.com/) e entre com sua conta do GitHub.
2. Clique em **"Add new site"** > **"Import an existing project"**.
3. Escolha o repositório `marlonferreira1800-hue/asclepio.face`.
4. Como o projeto já possui o [`netlify.toml`](file:///c:/Users/marlo/Downloads/Face%20inteligente/netlify.toml), basta clicar em **Deploy**.
5. O site será publicado instantaneamente com HTTPS e permissão de webcam!

## Instalação Desktop (Windows)

Recomenda-se Python 3.11. O MediaPipe ainda pode não oferecer pacote para todas as versões mais recentes do Python; nesse caso, o aplicativo usa o modo reduzido do OpenCV.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-optional.txt  # opcional: MediaPipe
python app.py
```

Se o MediaPipe falhar durante a instalação em uma versão incompatível, ignore a segunda instalação; o app continuará funcional, mas sem piscadas e pontos faciais:

```powershell
python app.py
```

## Uso recomendado

1. Posicione-se de frente, com luz uniforme, câmera estável e rosto centralizado.
2. Inicie a câmera e aceite o aviso de consentimento.
3. Inicie a linha de base e permaneça em repouso por 60–90 segundos.
4. Observe primeiro os indicadores de qualidade. Sem sinal suficiente, nenhum nível é produzido.
5. Interprete mudanças apenas como variações experimentais em relação à sua linha de base.
6. Marque “Salvar somente métricas ao parar” apenas se quiser manter a sessão localmente.

## Como o indicador funciona

Durante a calibração, o programa calcula média e desvio-padrão individual de piscadas por minuto, movimento da cabeça e pulso experimental disponível. Depois, converte aumentos em relação à linha de base em contribuições limitadas entre 0 e 1:

| Métrica | Peso máximo | Disponibilidade |
|---|---:|---|
| Piscadas por minuto | 25% | requer MediaPipe |
| Movimento da cabeça | 35% | MediaPipe ou Haar |
| Pulso rPPG experimental | 40% | somente com pico espectral confiável |

Os pesos disponíveis são renormalizados. Abaixo de 0,28 o estado é `estável`; de 0,28 a 0,62, `moderada`; acima disso, `elevada`. Qualidade inferior a 0,55 ou linha de base insuficiente sempre produz `medição insuficiente`. Esses limiares são heurísticos e precisam de validação; não são limites clínicos.

## rPPG experimental

A média do canal verde de uma pequena região da testa é coletada por cerca de 8–12 segundos. O sinal é reamostrado, tem a tendência removida e recebe uma FFT na faixa de 45–180 bpm. O valor só aparece quando o pico concentra pelo menos 35% da energia da banda. Movimento, compressão, iluminação variável, câmera automática e tons de pele podem introduzir viés ou inviabilizar a estimativa. A leitura não deve ser usada como medição médica.

## Arquitetura

```text
app.py                       entrada e erro amigável de dependência
src/ui/                      janela, consentimento, cards, sessões e worker assíncrono (QThread)
src/camera.py                captura OpenCV
src/face_tracker.py          MediaPipe + fallback Haar
src/blink_detector.py        EAR, eventos de piscada e extrapolação temporal
src/motion_analyzer.py       deslocamento facial normalizado
src/pulse_estimator.py       rPPG experimental e confiança
src/signal_quality.py        bloqueio por qualidade
src/calibration.py           linha de base individual
src/activation_model.py      regra transparente
src/session_store.py         SQLite/CSV local
tests/                       testes unitários sem webcam (18 testes)
```

## Testes e validação

Os testes usam dados sintéticos e a biblioteca padrão; não precisam de webcam nem da interface:

```powershell
python -m unittest discover -s tests -v
python -m compileall app.py src tests
```

Roteiro manual antes de qualquer uso experimental:

1. testar câmera presente, ausente e desconectada durante a sessão;
2. testar luz baixa, contraluz, desfoque e movimento para confirmar o bloqueio;
3. comparar piscadas com contagem manual em vídeos consentidos e diversos;
4. comparar o rPPG com um dispositivo de referência, estratificando iluminação, câmera e diversidade de pele;
5. verificar repetibilidade da linha de base em diferentes dias;
6. revisar falsos estados e nunca converter os resultados em rótulos psicológicos;
7. confirmar que nenhum arquivo de imagem/vídeo é criado e que a exclusão remove a sessão.

## Empacotamento futuro

Depois de validar no ambiente de destino:

```powershell
pip install -r requirements-dev.txt
pyinstaller --clean face_inteligente.spec
```

O executável aparecerá em `dist/FaceInteligente.exe` com ícone personalizado de `assets/icon.ico`. O empacotamento deve ser testado em uma máquina Windows limpa e não substitui assinatura de código ou revisão de privacidade.

## Limitações conhecidas

- O fallback Haar encontra a face, mas não fornece piscadas nem pontos detalhados.
- rPPG por webcam é sensível e pode ficar oculto durante grande parte de uma sessão.
- Os limiares e pesos são heurísticos, sem validação clínica ou populacional.
- Não há criptografia adicional do banco; ele herda a proteção da conta e do disco do Windows.
- O protótipo acompanha apenas um rosto por vez.

