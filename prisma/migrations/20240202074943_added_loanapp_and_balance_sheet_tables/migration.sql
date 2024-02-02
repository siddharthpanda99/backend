-- CreateTable
CREATE TABLE "loan_applications" (
    "loan_id" SERIAL NOT NULL,
    "companyName" TEXT NOT NULL,
    "provider" INTEGER NOT NULL,
    "loan_amt" INTEGER NOT NULL,
    "approved" BOOLEAN NOT NULL,
    "preAssessment" TEXT NOT NULL,
    "initiation_date" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "processing_date" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "loan_applications_pkey" PRIMARY KEY ("loan_id")
);

-- CreateTable
CREATE TABLE "bal_sheet" (
    "bal_sheet_id" SERIAL NOT NULL,
    "companyName" TEXT NOT NULL,
    "year" INTEGER NOT NULL,
    "month" INTEGER NOT NULL,
    "profitOrLoss" INTEGER NOT NULL,
    "assetsValue" INTEGER NOT NULL,

    CONSTRAINT "bal_sheet_pkey" PRIMARY KEY ("bal_sheet_id")
);
