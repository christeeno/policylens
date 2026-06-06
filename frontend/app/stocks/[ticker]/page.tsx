import StockDetailPage from "@/components/StockDetailPage";

export default function StockDetailRoute({
  params,
}: {
  params: { ticker: string };
}) {
  return <StockDetailPage ticker={decodeURIComponent(params.ticker).toUpperCase()} />;
}
