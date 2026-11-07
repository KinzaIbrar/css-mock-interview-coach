import '@testing-library/jest-dom/vitest'

// jsdom has no canvas: WebGL detection must see "unsupported" without console noise.
HTMLCanvasElement.prototype.getContext = (() => null) as typeof HTMLCanvasElement.prototype.getContext
