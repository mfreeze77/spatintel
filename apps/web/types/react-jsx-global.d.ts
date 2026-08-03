import type { JSX as ReactJSX } from "react";

// Next's generated typed-route declarations still refer to the pre-React 19
// global JSX namespace. Keep that narrow generated-code compatibility surface
// without weakening type checking for application code.
declare global {
  namespace JSX {
    type Element = ReactJSX.Element;
  }
}

export {};
