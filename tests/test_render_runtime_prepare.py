from core.render.render_runtime import RenderRuntime


runtime = RenderRuntime()


payload = {

    "architectural_intent": {

        "building_type":"house",
        "style":"traditional",
        "materials":[
            "brick"
        ],
        "environment":[
            "river"
        ]

    },

    "prompt":
        "small traditional brick house near river",

}


result = runtime.render(

    project_id="TEST001",

    design=payload,

    engine="flux"

)


print("\n===== RESULT =====")
print(result)