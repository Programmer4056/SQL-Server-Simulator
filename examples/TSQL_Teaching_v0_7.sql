-- SQL Server Simulator v0.7.0 educational compatibility example
-- CREATE DATABASE and USE map to local SQLite project files.
CREATE DATABASE Training;
GO
USE Training;
GO
CREATE TABLE [dbo].[Students] (
    [StudentID] INT IDENTITY(100,5) PRIMARY KEY,
    [FullName] NVARCHAR(80) NOT NULL
);
GO
-- The next statements are SIMULATED METADATA, NOT actual security enforcement.
CREATE USER demo_student WITHOUT LOGIN;
GRANT SELECT, INSERT ON dbo.Students TO demo_student;
DENY DELETE ON dbo.Students TO demo_student;
GO
INSERT INTO [dbo].[Students] ([FullName]) VALUES (N'Ali');
INSERT INTO [dbo].[Students] ([FullName]) VALUES (N'Sara');
SELECT * FROM [dbo].[Students];
