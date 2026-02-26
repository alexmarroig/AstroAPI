// This function is used to prevent a hydration error in React Navigation v6.
export function useClientOnlyValue<S, T>(web: S, native: T): S | T {
  return native;
}
