import { render, screen } from "@testing-library/react";
import HomePage from "@/app/page";

describe("HomePage", () => {
  it("renders the title and synthetic-data notice", () => {
    render(<HomePage />);
    expect(screen.getByRole("heading", { name: /incrementality drift monitor/i })).toBeInTheDocument();
    expect(screen.getByText(/synthetic/i)).toBeInTheDocument();
  });
});
