import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AppErrorBoundary } from "../AppErrorBoundary";

function BrokenView(): never {
  throw new Error("sensitive runtime detail");
}

describe("AppErrorBoundary", () => {
  it("shows a recoverable UI without exposing the runtime error", () => {
    const reload = vi.fn();
    vi.spyOn(console, "error").mockImplementation(() => undefined);

    render(
      <AppErrorBoundary onReload={reload}>
        <BrokenView />
      </AppErrorBoundary>,
    );

    expect(
      screen.getByRole("heading", { name: "화면을 불러오지 못했습니다." }),
    ).toBeTruthy();
    expect(screen.queryByText("sensitive runtime detail")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "새로고침" }));
    expect(reload).toHaveBeenCalledOnce();
    vi.restoreAllMocks();
  });
});
