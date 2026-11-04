import { ErroDaApi, criarCliente } from "./cliente";

type Resposta = { status?: number; corpo?: unknown; texto?: string; cabecalhos?: HeadersInit };

function respostaDe({ status = 200, corpo, texto, cabecalhos }: Resposta = {}): Response {
  const conteudo = texto ?? (corpo === undefined ? null : JSON.stringify(corpo));
  return new Response(status === 204 ? null : conteudo, {
    status,
    headers: { "Content-Type": "application/json", ...cabecalhos },
  });
}

function clienteCom(
  resposta: Response | Error,
  token: string | null = "segredo",
  extra: { equipeId?: () => number | null } = {},
) {
  const fetchFalso = vi.fn<typeof fetch>(async () => {
    if (resposta instanceof Error) throw resposta;
    // Um Response só pode ser lido uma vez; cada chamada recebe a sua cópia.
    return resposta.clone();
  });
  const cliente = criarCliente({
    urlBase: "http://127.0.0.1:8000",
    obterToken: async () => token,
    fetch: fetchFalso,
    ...extra,
  });
  return { cliente, fetchFalso };
}

function ultimaChamada(fetchFalso: ReturnType<typeof vi.fn<typeof fetch>>) {
  const [url, init] = fetchFalso.mock.calls[0] ?? [];
  return { url: String(url), init: init ?? {}, cabecalhos: new Headers(init?.headers) };
}

describe("criarCliente", () => {
  describe("cabeçalhos", () => {
    it("envia o token de acesso como Bearer", async () => {
      const { cliente, fetchFalso } = clienteCom(respostaDe({ corpo: [] }));

      await cliente.listarFormularios();

      expect(ultimaChamada(fetchFalso).cabecalhos.get("Authorization")).toBe("Bearer segredo");
    });

    it("não manda Authorization quando não há token (páginas públicas)", async () => {
      const { cliente, fetchFalso } = clienteCom(respostaDe({ corpo: [] }), null);

      await cliente.documentosLegais();

      expect(ultimaChamada(fetchFalso).cabecalhos.has("Authorization")).toBe(false);
    });

    it("manda a equipe ativa em X-Equipe, para o servidor conferir a pertença", async () => {
      const { cliente, fetchFalso } = clienteCom(respostaDe({ corpo: [] }), "t", {
        equipeId: () => 4,
      });

      await cliente.listarFormularios();

      expect(ultimaChamada(fetchFalso).cabecalhos.get("X-Equipe")).toBe("4");
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
      const cliente = criarCliente({ urlBase: "http://x.test/", fetch: fetchFalso });

      await cliente.listarFormularios();

      expect(String(fetchFalso.mock.calls[0]?.[0])).toBe("http://x.test/formularios");
    });

    it("com URL base vazia usa caminhos relativos (front servido pelo backend)", async () => {
      const fetchFalso = vi.fn<typeof fetch>(async () => respostaDe({ corpo: [] }));
      const cliente = criarCliente({ urlBase: "", fetch: fetchFalso });

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
      await cliente.atualizarRegistro(8, { a: 2 }, 3);
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
        ["PUT", "/registros/8", { dados: { a: 2 }, revisao: 3 }],
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

describe("pastas", () => {
  it("lista as pastas em lista plana", async () => {
    const { cliente, fetchFalso } = clienteCom(respostaDe({ corpo: [] }));

    await cliente.listarPastas();

    const { url, init } = ultimaChamada(fetchFalso);
    expect(url).toBe("http://127.0.0.1:8000/pastas");
    expect(init.method).toBe("GET");
  });

  it("cria na raiz mandando pasta_pai_id nulo, e dentro de outra com o id dela", async () => {
    const { cliente, fetchFalso } = clienteCom(respostaDe({ status: 201, corpo: {} }));

    await cliente.criarPasta("Obras", null);
    const naRaiz = JSON.parse(String(ultimaChamada(fetchFalso).init.body));
    await cliente.criarPasta("Fundação", 4);
    const dentro = JSON.parse(String(fetchFalso.mock.calls[1]?.[1]?.body));

    expect(naRaiz).toEqual({ nome: "Obras", pasta_pai_id: null });
    expect(dentro).toEqual({ nome: "Fundação", pasta_pai_id: 4 });
  });

  it("renomeia e move com PUT mandando os dois campos", async () => {
    const { cliente, fetchFalso } = clienteCom(respostaDe({ corpo: {} }));

    await cliente.atualizarPasta(7, "Estacas", null);

    const { url, init } = ultimaChamada(fetchFalso);
    expect(url).toBe("http://127.0.0.1:8000/pastas/7");
    expect(init.method).toBe("PUT");
    expect(JSON.parse(String(init.body))).toEqual({ nome: "Estacas", pasta_pai_id: null });
  });

  it("exclui a pasta (204 sem corpo)", async () => {
    const { cliente, fetchFalso } = clienteCom(respostaDe({ status: 204 }));

    await cliente.excluirPasta(7);

    const { url, init } = ultimaChamada(fetchFalso);
    expect(url).toBe("http://127.0.0.1:8000/pastas/7");
    expect(init.method).toBe("DELETE");
  });

  it("move o formulário para uma pasta ou para a raiz (pasta_id nulo)", async () => {
    const { cliente, fetchFalso } = clienteCom(respostaDe({ corpo: {} }));

    await cliente.moverFormulario(3, 9);
    const { url, init } = ultimaChamada(fetchFalso);
    await cliente.moverFormulario(3, null);
    const naRaiz = JSON.parse(String(fetchFalso.mock.calls[1]?.[1]?.body));

    expect(url).toBe("http://127.0.0.1:8000/formularios/3/pasta");
    expect(init.method).toBe("PUT");
    expect(JSON.parse(String(init.body))).toEqual({ pasta_id: 9 });
    expect(naRaiz).toEqual({ pasta_id: null });
  });

  it("criar formulário já dentro de uma pasta manda pasta_id", async () => {
    const { cliente, fetchFalso } = clienteCom(respostaDe({ status: 201, corpo: {} }));

    await cliente.criarFormulario({ nome: "ensaio", definicao: { campos: [] }, pasta_id: 5 });

    expect(JSON.parse(String(ultimaChamada(fetchFalso).init.body))).toEqual({
      nome: "ensaio",
      definicao: { campos: [] },
      pasta_id: 5,
    });
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

describe("renovação do token", () => {
  const expirado = () =>
    respostaDe({
      status: 401,
      corpo: { detalhe: "Sua sessão expirou.", erros: [], codigo: "token_expirado" },
    });

  it("renova uma vez ao receber token_expirado e repete a chamada com o token novo", async () => {
    const respostas = [expirado(), respostaDe({ corpo: [] })];
    const fetchFalso = vi.fn<typeof fetch>(async () => respostas.shift()!);
    const renovarToken = vi.fn(async () => "novo");
    const cliente = criarCliente({
      urlBase: "http://x.test",
      obterToken: async () => "velho",
      renovarToken,
      fetch: fetchFalso,
    });

    await cliente.listarFormularios();

    expect(renovarToken).toHaveBeenCalledTimes(1);
    expect(fetchFalso).toHaveBeenCalledTimes(2);
    expect(new Headers(fetchFalso.mock.calls[1]?.[1]?.headers).get("Authorization")).toBe(
      "Bearer novo",
    );
  });

  it("não insiste: se o token novo também for recusado, o erro sobe", async () => {
    const fetchFalso = vi.fn<typeof fetch>(async () => expirado());
    const cliente = criarCliente({
      urlBase: "http://x.test",
      obterToken: async () => "velho",
      renovarToken: async () => "novo",
      fetch: fetchFalso,
    });

    await expect(cliente.listarFormularios()).rejects.toMatchObject({
      status: 401,
      codigo: "token_expirado",
    });
    expect(fetchFalso).toHaveBeenCalledTimes(2);
  });

  it("401 que não é de expiração não renova", async () => {
    const renovarToken = vi.fn(async () => "novo");
    const cliente = criarCliente({
      urlBase: "http://x.test",
      obterToken: async () => "t",
      renovarToken,
      fetch: vi.fn<typeof fetch>(async () =>
        respostaDe({
          status: 401,
          corpo: { detalhe: "Token inválido.", erros: [], codigo: "token_invalido" },
        }),
      ),
    });

    await expect(cliente.listarFormularios()).rejects.toBeInstanceOf(ErroDaApi);
    expect(renovarToken).not.toHaveBeenCalled();
  });

  it("guarda o código do erro para a tela decidir (ex.: termos pendentes)", async () => {
    const { cliente } = clienteCom(
      respostaDe({
        status: 403,
        corpo: { detalhe: "Aceite os termos.", erros: [], codigo: "termos_pendentes" },
      }),
    );

    await expect(cliente.eu()).rejects.toMatchObject({ status: 403, codigo: "termos_pendentes" });
  });
});
