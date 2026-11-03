import { Cartao, Carregando, Esqueleto } from "../ui";

/*
 * Cada esqueleto tem a forma da tela que vai aparecer (mesmas alturas e larguras), para a
 * página não "pular" quando o dado chega.
 */

export function EsqueletoDaLista() {
  return (
    <Carregando rotulo="Carregando formulários">
      <Cartao>
        <ul className="divide-y divide-pedra-200">
          {[0, 1, 2].map((i) => (
            <li key={i} className="flex flex-wrap items-center gap-x-4 gap-y-2 p-4">
              <div className="mr-auto flex min-h-12 items-center gap-3">
                <Esqueleto className="size-9" />
                <div className="flex flex-col gap-2">
                  <Esqueleto className="h-4 w-44" />
                  <Esqueleto className="h-4 w-10" />
                </div>
              </div>
              <div className="flex gap-1.5">
                <Esqueleto className="h-7 w-24" />
                <Esqueleto className="h-7 w-20" />
                <Esqueleto className="h-7 w-16" />
                <Esqueleto className="h-7 w-20" />
              </div>
            </li>
          ))}
        </ul>
      </Cartao>
    </Carregando>
  );
}

export function EsqueletoDaTabela() {
  return (
    <Carregando rotulo="Carregando registros">
      <Cartao className="overflow-hidden">
        <div className="flex gap-6 border-b border-pedra-200 bg-pedra-100 px-4 py-3">
          {[28, 36, 24, 32].map((largura, i) => (
            <Esqueleto key={i} className="h-3.5" style={{ width: `${largura * 4}px` }} />
          ))}
        </div>
        {[0, 1, 2, 3, 4].map((i) => (
          <div key={i} className="flex gap-6 border-b border-pedra-200 px-4 py-3.5 last:border-0">
            {[28, 36, 24, 32].map((largura, j) => (
              <Esqueleto key={j} className="h-4" style={{ width: `${largura * 4}px` }} />
            ))}
          </div>
        ))}
      </Cartao>
    </Carregando>
  );
}

export function EsqueletoDoFormulario() {
  return (
    <Carregando rotulo="Carregando formulário">
      <div className="flex max-w-xl flex-col gap-5">
        <div className="flex flex-col gap-2">
          <Esqueleto className="h-7 w-72" />
          <Esqueleto className="h-4 w-40" />
        </div>
        {[0, 1, 2, 3, 4].map((i) => (
          <div key={i} className="flex flex-col gap-1.5">
            <Esqueleto className="h-4 w-32" />
            <Esqueleto className="h-9 w-full" />
          </div>
        ))}
        <div className="flex gap-2">
          <Esqueleto className="h-9 w-20" />
          <Esqueleto className="h-9 w-24" />
        </div>
      </div>
    </Carregando>
  );
}

export function EsqueletoDoConstrutor() {
  return (
    <Carregando rotulo="Carregando o construtor">
      <div className="flex flex-col gap-6">
        <div className="flex items-end justify-between">
          <Esqueleto className="h-8 w-64" />
          <Esqueleto className="h-10 w-44" />
        </div>
        <div className="grid grid-cols-[13rem_1fr_22rem] gap-6">
          <div className="flex flex-col gap-2">
            <Esqueleto className="mb-1 h-5 w-28" />
            {Array.from({ length: 10 }, (_, i) => (
              <Esqueleto key={i} className="h-9 w-full" />
            ))}
          </div>
          <div className="flex flex-col gap-2">
            <Esqueleto className="mb-1 h-5 w-20" />
            {Array.from({ length: 6 }, (_, i) => (
              <Esqueleto key={i} className="h-10 w-full" />
            ))}
          </div>
          <Esqueleto className="h-48 w-full" />
        </div>
      </div>
    </Carregando>
  );
}
