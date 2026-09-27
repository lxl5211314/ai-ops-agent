import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import PatchViewer from "../src/components/PatchViewer";
import PathConnectForm from "../src/components/PathConnectForm";

describe("PatchViewer", () => {
  it("renders applicable badge and patch text", () => {
    render(
      <PatchViewer patch={"--- a/app.py\n+++ b/app.py\n"} applicable={true} validationLog="ok" />,
    );
    expect(screen.getByText(/补丁校验通过/)).toBeInTheDocument();
    expect(screen.getByText(/a\/app\.py/)).toBeInTheDocument();
    expect(screen.getByText("复制补丁")).toBeInTheDocument();
  });

  it("renders failure state when patch missing", () => {
    render(<PatchViewer patch={null} applicable={null} />);
    expect(screen.getByText("本次分析未生成补丁")).toBeInTheDocument();
  });

  it("renders unapplied warning badge", () => {
    render(<PatchViewer patch={"--- a/x\n+++ b/x\n"} applicable={false} />);
    expect(screen.getByText(/补丁校验未通过/)).toBeInTheDocument();
  });
});

describe("PathConnectForm", () => {
  it("disables submit until path entered", async () => {
    const onSubmit = vi.fn();
    render(<PathConnectForm onSubmit={onSubmit} />);
    const button = screen.getByTestId("path-submit");
    expect(button).toBeDisabled();
    fireEvent.change(screen.getByTestId("path-input"), {
      target: { value: "/workspace/svc" },
    });
    expect(button).toBeEnabled();
    fireEvent.click(button);
    expect(onSubmit).toHaveBeenCalledWith("/workspace/svc", "");
  });
});
