-- SQL Server Simulator v0.8.3: Views, Procedures and Functions
-- These statements are an EDUCATIONAL SUBSET, not the SQL Server engine.
-- CREATE statements are GO-delimited batches; keep GO on its own line.

CREATE DATABASE ModuleTraining;
GO
USE ModuleTraining;
GO
CREATE TABLE dbo.Students (
    ID INT IDENTITY(10,5) PRIMARY KEY,
    Name NVARCHAR(50) NOT NULL
);
GO

-- A real, persisted SQLite view (queryable with SELECT).
CREATE VIEW dbo.vStudentNames AS SELECT ID, Name FROM dbo.Students;
GO

-- Persisted educational procedure; input values are safely bound.
CREATE PROC dbo.AddStudent @Name NVARCHAR(50)
AS
BEGIN
    SET NOCOUNT ON;
    INSERT INTO dbo.Students(Name) VALUES(@Name);
    SELECT ID, Name FROM dbo.Students;
END;
GO

-- Persistent scalar function; expression evaluated by SQLite.
CREATE FUNCTION dbo.DoubleID(@Number INT)
RETURNS INT
AS
BEGIN
    RETURN @Number * 2;
END;
GO

EXEC dbo.AddStudent @Name=N'علی';
GO
EXEC dbo.AddStudent @Name=N'سارا';
GO
SELECT ID, Name, dbo.DoubleID(ID) AS Double_ID
FROM dbo.vStudentNames ORDER BY ID;
