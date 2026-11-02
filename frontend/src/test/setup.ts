import "@testing-library/jest-dom/vitest";

// O jsdom não implementa estas duas; as miniaturas de foto dependem delas.
URL.createObjectURL = vi.fn(() => "blob:miniatura-de-teste");
URL.revokeObjectURL = vi.fn();
