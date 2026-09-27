import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import Uploader from "../src/components/Uploader";

const file = new File(["print('x')"], "main.py", { type: "text/x-python" });

describe("Uploader", () => {
  it("stays disabled until files are selected and uploads on click", () => {
    const onUpload = vi.fn().mockResolvedValue(undefined);
    render(<Uploader onUpload={onUpload} />);
    const button = screen.getByRole("button", { name: /上传源码/ });
    expect(button).toBeDisabled();

    fireEvent.change(screen.getByTestId("uploader-input"), { target: { files: [file] } });
    expect(screen.getByText("已选择 1 个文件")).toBeInTheDocument();
    expect(button).toBeEnabled();

    fireEvent.click(button);
    expect(onUpload).toHaveBeenCalledWith([file]);
  });

  it("stays disabled while busy", () => {
    render(<Uploader onUpload={vi.fn()} busy />);
    expect(screen.getByRole("button", { name: /上传中/ })).toBeDisabled();
  });
});
