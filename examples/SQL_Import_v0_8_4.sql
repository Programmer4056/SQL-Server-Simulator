-- SQL Server Simulator v0.8.4: educational supported import sample
-- NOTE: This is a supported T-SQL subset, not a general SQL Server script.
CREATE DATABASE Training084;
GO
USE Training084;
GO
CREATE TABLE [dbo].[Departments] (
    [ID] [int] IDENTITY(1,1) NOT NULL PRIMARY KEY,
    [Title] [nvarchar](100) NOT NULL
);
GO
CREATE TABLE [dbo].[Students] (
    [ID] [int] IDENTITY(1,1) NOT NULL PRIMARY KEY,
    [FullName] [nvarchar](100) NOT NULL,
    [DepartmentID] [int] NULL
);
GO
ALTER TABLE [dbo].[Students] WITH CHECK ADD CONSTRAINT [FK_Students_Departments]
    FOREIGN KEY([DepartmentID]) REFERENCES [dbo].[Departments] ([ID]);
GO
INSERT INTO [Departments] ([Title]) VALUES (N'Engineering');
INSERT INTO [Students] ([FullName], [DepartmentID]) VALUES (N'Example Student', 1);
GO
SELECT * FROM [Students];
