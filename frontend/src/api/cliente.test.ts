import { ErroDaApi, configuracaoPadrao, criarCliente } from "./cliente";

type Resposta = { status?: number; corpo?: unknown; texto?: string; cabecalhos?: HeadersInit };

function respostaDe({ status = 200, corpo, texto, cabecalhos }: Resposta = {}): Response {
  const conteudo = texto ?? (corpo === undefined ? null : JSON.stringify(corpo));
  return new Response(status === 204 ? null : conteudo, {
    status,
    headers: { "Content-Type": "application/json", ...cabecalhos },
  });
}

function clienteCom(resposta: Response | Error, token: string | null = "segredo") {
  const fetchFalso = vi.fn<typeof fetch>(async () => {
    if (resposta instanceof Error) throw resposta;
    // Um Response só pode ser lido uma vez; cada chamada recebe a sua cópia.
    return resposta.clone();
  });
  const cliente = criarCliente({ urlBase: "http://127.0.0.1:8000", token, fetch: fetchFalso });
  return { cliente, fetchFalso };
}

function ultimaChamada(fetchFalso: ReturnType<typeof vi.fn<typeof fetch>>) {
  const [url, init] = fetchFalso.mock.calls[0] ?? [];
  return { url: String(url), init: init ?? {}, cabecalhos: new Headers(init?.headers) };
}

describe("criarCliente", () => {
  describe("cabeçalhos", () => {
    it("envia o token da execução no X-Forms-Token", async () => {
      const { cliente, fetchFalso } = clienteCom(respostaDe({ corpo: [] }));

      await cliente.listarFormularios();

      expect(ultimaChamada(fetchFalso).cabecalhos.get("X-Forms-Token")).toBe("segredo");
    });

    it("não manda o cabeçalho quando não há token (desenvolvimento)", async () => {
      const { cliente, fetchFalso } = clienteCom(respostaDe({ corpo: [] }), null);

      await cliente.listarFormularios();

      expect(ultimaChamada(fetchFalso).cabecalhos.has("X-Forms-Token")).toBe(false);
    });

    it("manda JSON com Content-Type quando há corpo", async () => {
      const { cliente, fetchFalso } = clienteCom(respostaDe({ status: 201, corpo: {} }));

      await cliente.criarFormulario({ nome: "ensaio", definicao: { campos: [] } });

      const { url, init, cabecalhos } = ultimaChamada(fetchFalso);
      expect(url).toBe("http://127.0.0.1:8000/formularios");
      expect(init.method).toBe("POST");
      expect(cabecalhos.get("Content-Type")).toBe("application/json");
      expect(JSON.parse(String(init.body))).toEqual({ nome: "ensaio", definicao: { campos: [] } });
    });
  });

  describe("URL", () => {
    it("ignora a barra final da URL base", async () => {
      const fetchFalso = vi.fn<typeof fetch>(async () => respostaDe({ corpo: [] }));
      const cliente = criarCliente({ urlBase: "http://x.test/", token: null, fetch: fetchFalso });

      await cliente.listarFormularios();

      expect(String(fetchFalso.mock.calls[0]?.[0])).toBe("http://x.test/formularios");
    });

    it("com URL base vazia usa caminhos relativos (front servido pelo backend)", async () => {
      const fetchFalso = vi.fn<typeof fetch>(async () => respostaDe({ corpo: [] }));
      const cliente = criarCliente({ urlBase: "", token: null, fetch: fetchFalso });

      await cliente.listarFormularios();

      expect(String(fetchFalso.mock.calls[0]?.[0])).toBe("/formularios");
    });

    it("monta a listagem com versão, janela, datas e filtros repetidos como campo:valor", async () => {
      const { cliente, fetchFalso } = clienteCom(
        respostaDe({ corpo: { versao_id: 1, colunas: [], itens: [], total: 0 } }),
      );

      await cliente.listarRegistros(7, {
        versaoId: 3,
        limite: 20,
        deslocamento: 40,
        criadoDe: "2026-11-01",
        criadoAte: "2026-11-30",
        filtros: { resultado: "Aprovado", conforme: "true" },
      });

      const url = new URL(ultimaChamada(fetchFalso).url);
      expect(url.pathname).toBe("/formularios/7/registros");
      expect(url.searchParams.get("versao_id")).toBe("3");
      expect(url.searchParams.get("limite")).toBe("20");
      expect(url.searchParams.get("deslocamento")).toBe("40");
      expect(url.searchParams.get("criado_de")).toBe("2026-11-01");
      expect(url.searchParams.get("criado_ate")).toBe("2026-11-30");
      expect(url.searchParams.getAll("filtro")).toEqual(["resultado:Aprovado", "conforme:true"]);
    });

    it("não põe parâmetros que não foram pedidos", async () => {
      const { cliente, fetchFalso } = clienteCom(
        respostaDe({ corpo: { versao_id: 1, colunas: [], itens: [], total: 0 } }),
      );

      await cliente.listarRegistros(7);

      expect(ultimaChamada(fetchFalso).url).toBe("http://127.0.0.1:8000/formularios/7/registros");
    });

    it("escapa o valor do filtro", async () => {
      const { cliente, fetchFalso } = clienteCom(
        respostaDe({ corpo: { versao_id: 1, colunas: [], itens: [], total: 0 } }),
      );

      await cliente.listarRegistros(1, { filtros: { obs: "a&b=c d" } });

      const url = new URL(ultimaChamada(fetchFalso).url);
      expect(url.searchParams.getAll("filtro")).toEqual(["obs:a&b=c d"]);
    });
  });

  describe("erro uniforme", () => {
    it("vira um objeto tipado com status, detalhe e erros por campo", async () => {
      const erros = [
        {
          campo: "resistencia.formula",
          mensagem: "Divisão inválida",
          posicao: { inicio: 2, fim: 9 },
        },
        { campo: "nome", mensagem: "Campo obrigatório." },
      ];
      const { cliente } = clienteCom(
        respostaDe({ status: 422, corpo: { detalhe: "Definição inválida.", erros } }),
      );

      const falha = await cliente
        .criarFormulario({ nome: "", definicao: {} })
        .catch((e: unknown) => e);

      expect(falha).toBeInstanceOf(ErroDaApi);
      const erro = falha as ErroDaApi;
      expect(erro.status).toBe(422);
      expect(erro.message).toBe("Definição inválida.");
      expect(erro.erros).toEqual(erros);
      expect(erro.erros[0]?.posicao).toEqual({ inicio: 2, fim: 9 });
    });

    it("agrupa as mensagens por campo para o formulário mostrar no lugar certo", async () => {
      const { cliente } = clienteCom(
        respostaDe({
          status: 422,
          corpo: {
            detalhe: "Registro inválido.",
            erros: [
              { campo: "fck", mensagem: "Campo obrigatório." },
              { campo: "fck", mensagem: "Deve ser um número." },
              { campo: "data", mensagem: "Data inválida." },
            ],
          },
        }),
      );

      const erro = (await cliente.obterRegistro(1).catch((e: unknown) => e)) as ErroDaApi;

      expect(erro.mensagensPorCampo()).toEqual({
        fck: ["Campo obrigatório.", "Deve ser um número."],
        data: ["Data inválida."],
      });
    });

    it.each([
      [401, "Token ausente ou inválido."],
      [404, "Registro 9 não encontrado."],
      [409, "O registro 9 é referenciado."],
    ])("trata %i com a mensagem do servidor e sem erros por campo", async (status, detalhe) => {
      const { cliente } = clienteCom(respostaDe({ status, corpo: { detalhe, erros: [] } }));

      const erro = (await cliente.obterRegistro(9).catch((e: unknown) => e)) as ErroDaApi;

      expect(erro.status).toBe(status);
      expect(erro.message).toBe(detalhe);
      expect(erro.erros).toEqual([]);
    });

    it("não quebra quando o corpo do erro não é o formato uniforme", async () => {
      const { cliente } = clienteCom(
        respostaDe({
          status: 502,
          texto: "<html>Bad gateway</html>",
          cabecalhos: { "Content-Type": "text/html" },
        }),
      );

      const erro = (await cliente.listarFormularios().catch((e: unknown) => e)) as ErroDaApi;

      expect(erro).toBeInstanceOf(ErroDaApi);
      expect(erro.status).toBe(502);
      expect(erro.message).toBe("Erro 502 ao falar com o servidor.");
    });

    it("erro interno do servidor mostra a mensagem dele, não a de falta de conexão", async () => {
      const { cliente } = clienteCom(
        respostaDe({ status: 500, corpo: { detalhe: "Erro interno do servidor.", erros: [] } }),
      );

      const erro = (await cliente.listarFormularios().catch((e: unknown) => e)) as ErroDaApi;

      expect(erro).toBeInstanceOf(ErroDaApi);
      expect(erro.status).toBe(500);
      expect(erro.message).toBe("Erro interno do servidor.");
    });

    it("sem conexão, vira um erro claro em português com status 0", async () => {
      const { cliente } = clienteCom(new TypeError("Failed to fetch"));

      const erro = (await cliente.listarFormularios().catch((e: unknown) => e)) as ErroDaApi;

      expect(erro).toBeInstanceOf(ErroDaApi);
      expect(erro.status).toBe(0);
      expect(erro.message).toMatch(/Não foi possível conectar/);
    });
  });

  describe("respostas", () => {
    it("devolve o corpo JSON tipado", async () => {
      const resumo = {
        id: 1,
        nome: "ensaio",
        criado_em: "2026-11-02T10:00:00+00:00",
        versao_atual_id: 1,
        versao_atual_numero: 1,
      };
      const { cliente } = clienteCom(respostaDe({ corpo: [resumo] }));

      const lista = await cliente.listarFormularios();

      expect(lista[0]?.nome).toBe("ensaio");
    });

    it("trata 204 (exclusão) como sucesso sem corpo", async () => {
      const { cliente, fetchFalso } = clienteCom(respostaDe({ status: 204 }));

      await expect(cliente.excluirRegistro(3)).resolves.toBeUndefined();
      expect(ultimaChamada(fetchFalso).init.method).toBe("DELETE");
    });

    it("baixa o CSV como arquivo, com o nome vindo do servidor", async () => {
      const { cliente } = clienteCom(
        new Response("a;b\r\n", {
          headers: {
            "Content-Type": "text/csv; charset=utf-8",
            "Content-Disposition": 'attachment; filename="corpo_de_prova.csv"',
          },
        }),
      );

      const arquivo = await cliente.exportarRegistros(1, { filtros: { obs: "x" } });

      expect(arquivo.nome).toBe("corpo_de_prova.csv");
      expect(await arquivo.blob.text()).toBe("a;b\r\n");
    });

    it("usa um nome padrão quando o servidor não manda o nome do CSV", async () => {
      const { cliente } = clienteCom(
        new Response("x", { headers: { "Content-Type": "text/csv" } }),
      );

      expect((await cliente.exportarRegistros(1)).nome).toBe("registros.csv");
    });

    it("lê a foto como Blob (a imagem não pode ir num <img src> porque não leva o token)", async () => {
      const { cliente, fetchFalso } = clienteCom(
        new Response(new Uint8Array([1, 2, 3]), { headers: { "Content-Type": "image/webp" } }),
      );

      const blob = await cliente.obterAnexo(5);

      expect(blob.type).toBe("image/webp");
      expect(ultimaChamada(fetchFalso).url).toBe("http://127.0.0.1:8000/anexos/5");
      expect(ultimaChamada(fetchFalso).cabecalhos.get("X-Forms-Token")).toBe("segredo");
    });

    it("envia a foto como multipart no campo `arquivo`, sem fixar o Content-Type", async () => {
      const { cliente, fetchFalso } = clienteCom(
        respostaDe({ status: 201, corpo: { id: 1, largura: 10, altura: 10, tamanho_bytes: 100 } }),
      );
      const foto = new File([new Uint8Array([1])], "minha foto.jpg", { type: "image/jpeg" });

      const anexo = await cliente.enviarAnexo(foto);

      const { init, cabecalhos } = ultimaChamada(fetchFalso);
      expect(anexo.id).toBe(1);
      expect(init.body).toBeInstanceOf(FormData);
      expect((init.body as FormData).get("arquivo")).toBeInstanceOf(File);
      // O navegador precisa gerar o Content-Type com o `boundary` do multipart.
      expect(cabecalhos.has("Content-Type")).toBe(false);
    });
  });

  describe("endpoints", () => {
    it.each([
      [
        "obterFormulario",
        (c: ReturnType<typeof criarCliente>) => c.obterFormulario(4),
        "GET",
        "/formularios/4",
      ],
      [
        "listarVersoes",
        (c: ReturnType<typeof criarCliente>) => c.listarVersoes(4),
        "GET",
        "/formularios/4/versoes",
      ],
      [
        "obterVersao",
        (c: ReturnType<typeof criarCliente>) => c.obterVersao(4, 9),
        "GET",
        "/formularios/4/versoes/9",
      ],
      [
        "excluirFormulario",
        (c: ReturnType<typeof criarCliente>) => c.excluirFormulario(4),
        "DELETE",
        "/formularios/4",
      ],
      ["catalogo", (c: ReturnType<typeof criarCliente>) => c.catalogo(), "GET", "/catalogo"],
      [
        "obterRegistro",
        (c: ReturnType<typeof criarCliente>) => c.obterRegistro(2),
        "GET",
        "/registros/2",
      ],
    ])("%s chama %s %s", async (_nome, chamar, metodo, caminho) => {
      const { cliente, fetchFalso } = clienteCom(respostaDe({ corpo: {} }));

      await chamar(cliente);

      const { url, init } = ultimaChamada(fetchFalso);
      expect(init.method).toBe(metodo);
      expect(new URL(url).pathname).toBe(caminho);
    });

    it("publica versão, valida definição, pede prévia e cria/atualiza registro com os corpos certos", async () => {
      const { cliente, fetchFalso } = clienteCom(respostaDe({ corpo: {} }));

      await cliente.publicarVersao(1, { campos: [] });
      await cliente.validarDefinicao({ campos: [] });
      await cliente.previa({ campos: [] }, { a: 1 });
      await cliente.criarRegistro(1, 5, { a: 1 });
      await cliente.atualizarRegistro(8, { a: 2 });
      await cliente.criarFormulariosEmLote([{ nome: "a", definicao: {} }]);

      const chamadas = fetchFalso.mock.calls.map(([url, init]) => [
        init?.method,
        new URL(String(url)).pathname,
        JSON.parse(String(init?.body)),
      ]);
      expect(chamadas).toEqual([
        ["POST", "/formularios/1/versoes", { definicao: { campos: [] } }],
        ["POST", "/definicoes/validar", { definicao: { campos: [] } }],
        ["POST", "/definicoes/previa", { definicao: { campos: [] }, valores: { a: 1 } }],
        ["POST", "/formularios/1/registros", { versao_id: 5, dados: { a: 1 } }],
        ["PUT", "/registros/8", { dados: { a: 2 } }],
        ["POST", "/formularios/lote", { formularios: [{ nome: "a", definicao: {} }] }],
      ]);
    });
  });
});

describe("duplicarFormulario", () => {
  it("sem nome, faz POST sem corpo e devolve o formulário criado", async () => {
    const criado = { id: 9, nome: "ensaio (cópia)" };
    const { cliente, fetchFalso } = clienteCom(respostaDe({ status: 201, corpo: criado }));

    const resultado = await cliente.duplicarFormulario(3);

    const { url, init, cabecalhos } = ultimaChamada(fetchFalso);
    expect(url).toBe("http://127.0.0.1:8000/formularios/3/duplicar");
    expect(init.method).toBe("POST");
    expect(init.body).toBeUndefined();
    expect(cabecalhos.has("Content-Type")).toBe(false);
    expect(resultado).toEqual(criado);
  });

  it("com nome, manda `{nome}` como JSON", async () => {
    const { cliente, fetchFalso } = clienteCom(respostaDe({ status: 201, corpo: {} }));

    await cliente.duplicarFormulario(3, "Ensaio B");

    const { init, cabecalhos } = ultimaChamada(fetchFalso);
    expect(JSON.parse(String(init.body))).toEqual({ nome: "Ensaio B" });
    expect(cabecalhos.get("Content-Type")).toBe("application/json");
  });
});

describe("gerarFormularios", () => {
  it("manda o pedido e os rascunhos em edição e devolve os rascunhos propostos", async () => {
    const proposta = {
      formularios: [{ nome: "Ensaio", definicao: { campos: [] }, erros: [] }],
    };
    const { cliente, fetchFalso } = clienteCom(respostaDe({ corpo: proposta }));

    const resultado = await cliente.gerarFormularios({
      pedido: "um ensaio",
      rascunhos: [{ nome: "Ensaio", definicao: { campos: [] } }],
    });

    const { url, init } = ultimaChamada(fetchFalso);
    expect(url).toBe("http://127.0.0.1:8000/definicoes/gerar");
    expect(init.method).toBe("POST");
    expect(JSON.parse(String(init.body))).toEqual({
      pedido: "um ensaio",
      rascunhos: [{ nome: "Ensaio", definicao: { campos: [] } }],
    });
    expect(resultado).toEqual(proposta);
  });

  it("sem rascunhos manda a lista vazia", async () => {
    const { cliente, fetchFalso } = clienteCom(respostaDe({ corpo: { formularios: [] } }));

    await cliente.gerarFormularios({ pedido: "x" });

    expect(JSON.parse(String(ultimaChamada(fetchFalso).init.body))).toEqual({
      pedido: "x",
      rascunhos: [],
    });
  });

  it("IA indisponível chega como ErroDaApi 503 com a mensagem em português", async () => {
    const { cliente } = clienteCom(
      respostaDe({ status: 503, corpo: { detalhe: "A IA está indisponível.", erros: [] } }),
    );

    await expect(cliente.gerarFormularios({ pedido: "x" })).rejects.toMatchObject({
      status: 503,
      message: "A IA está indisponível.",
    });
  });
});

describe("configuracaoPadrao", () => {
  afterEach(() => {
    delete window.formsApi;
    vi.unstubAllEnvs();
  });

  it("usa o token e a URL do preload quando o Electron os expõe", () => {
    window.formsApi = { token: "do-preload", urlBase: "http://127.0.0.1:5555" };

    expect(configuracaoPadrao()).toMatchObject({
      token: "do-preload",
      urlBase: "http://127.0.0.1:5555",
    });
  });

  it("no instalado o front é servido pelo backend: sem URL no preload, caminhos relativos", () => {
    window.formsApi = { token: "do-preload" };

    expect(configuracaoPadrao()).toMatchObject({ token: "do-preload", urlBase: "" });
  });

  it("em desenvolvimento usa as variáveis do Vite", () => {
    vi.stubEnv("VITE_API_URL", "http://127.0.0.1:9000");
    vi.stubEnv("VITE_FORMS_TOKEN", "do-dev");

    expect(configuracaoPadrao()).toMatchObject({
      token: "do-dev",
      urlBase: "http://127.0.0.1:9000",
    });
  });

  it("sem nada configurado aponta para a API local e não manda token", () => {
    vi.stubEnv("VITE_API_URL", "");
    vi.stubEnv("VITE_FORMS_TOKEN", "");

    expect(configuracaoPadrao()).toMatchObject({ token: null, urlBase: "http://127.0.0.1:8000" });
  });
});
