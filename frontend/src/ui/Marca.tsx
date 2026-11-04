/** A marca é só o nome escrito, com o hífen no azul de ação: sem símbolo (design de referência). */
export function Marca({ className = "" }: { className?: string }) {
  return (
    <span className={`font-titulo font-extrabold tracking-tight ${className}`}>
      data<span className="text-sinal-500">-</span>collect
    </span>
  );
}
