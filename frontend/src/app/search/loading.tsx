import LoadingSpinner from "@/components/ui/LoadingSpinner";

export default function SearchLoading() {
  return (
    <div className="flex items-center justify-center min-h-[400px]">
      <LoadingSpinner size="lg" />
    </div>
  );
}
