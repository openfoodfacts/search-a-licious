const JsonSchemaStaticDocs = require("json-schema-static-docs");

(async () => {
  let jsonSchemaStaticDocs = new JsonSchemaStaticDocs({
    inputPath: "/docs",
    outputPath: "/docs",
    indexTitle: "Reference for configuration file",
    ajvOptions: {
      allowUnionTypes: true,
    },
  });
  await jsonSchemaStaticDocs.generate();
  console.log("Documents generated.");
})();