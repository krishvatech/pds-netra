import Image from 'next/image';

export type BrandLogoProps = {
  className?: string;
};

export function BrandLogo({ className }: BrandLogoProps) {
  return (
    <Image
      src="/kt-logo.png"
      alt="Krishvatech Private Limited"
      width={320}
      height={320}
      className={className}
      priority
    />
  );
}
